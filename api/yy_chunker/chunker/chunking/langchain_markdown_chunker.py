import re
from typing import List, Tuple, Union, Dict, Any

# Import Document type hint if needed for clarity, though we extract string content
from langchain_core.documents import Document
from .base_chunker import BaseChunker

# Optional: If you need a specific length function like openai_token_count
# from ..utils import openai_token_count


class ExperimentalMarkdownSyntaxTextSplitter:
    """An experimental text splitter for handling Markdown syntax.

    This splitter aims to retain the exact whitespace of the original text while
    extracting structured metadata, such as headers. It is a re-implementation of the
    MarkdownHeaderTextSplitter with notable changes to the approach and
    additional features.

    Key Features:
    - Retains the original whitespace and formatting of the Markdown text.
    - Extracts headers, code blocks, and horizontal rules as metadata.
    - Splits out code blocks and includes the language in the "Code" metadata key.
    - Splits text on horizontal rules (`---`) as well.
    - Defaults to sensible splitting behavior, which can be overridden using the
      `headers_to_split_on` parameter.

    Parameters:
    ----------
    headers_to_split_on : List[Tuple[str, str]], optional
        Headers to split on, defaulting to common Markdown headers if not specified.
    return_each_line : bool, optional
        When set to True, returns each line as a separate chunk. Default is False.

    Usage example:
    --------------
    >>> headers_to_split_on = [
    >>>     ("#", "Header 1"),
    >>>     ("##", "Header 2"),
    >>> ]
    >>> splitter = ExperimentalMarkdownSyntaxTextSplitter(
    >>>     headers_to_split_on=headers_to_split_on
    >>> )
    >>> chunks = splitter.split(text)
    >>> for chunk in chunks:
    >>>     print(chunk)

    This class is currently experimental and subject to change based on feedback and
    further development.
    """

    DEFAULT_HEADER_KEYS = {
        "#": "Header 1",
        "##": "Header 2",
        "###": "Header 3",
        "####": "Header 4",
        "#####": "Header 5",
        "######": "Header 6",
    }

    def __init__(
        self,
        headers_to_split_on: Union[List[Tuple[str, str]], None] = None,
        return_each_line: bool = False,
        strip_headers: bool = True,
    ):
        """Initialize the text splitter with header splitting and formatting options.

        This constructor sets up the required configuration for splitting text into
        chunks based on specified headers and formatting preferences.

        Args:
            headers_to_split_on (Union[List[Tuple[str, str]], None]):
                A list of tuples, where each tuple contains a header tag (e.g., "h1")
                and its corresponding metadata key. If None, default headers are used.
            return_each_line (bool):
                Whether to return each line as an individual chunk.
                Defaults to False, which aggregates lines into larger chunks.
            strip_headers (bool):
                Whether to exclude headers from the resulting chunks.
                Defaults to True.
        """
        self.chunks: List[Document] = []
        self.current_chunk = Document(page_content="")
        self.current_header_stack: List[Tuple[int, str]] = []
        self.strip_headers = strip_headers
        if headers_to_split_on:
            self.splittable_headers = dict(headers_to_split_on)
        else:
            self.splittable_headers = self.DEFAULT_HEADER_KEYS

        self.return_each_line = return_each_line

    def split_text(self, text: str) -> List[Document]:
        """Split the input text into structured chunks.

        This method processes the input text line by line, identifying and handling
        specific patterns such as headers, code blocks, and horizontal rules to
        split it into structured chunks based on headers, code blocks, and
        horizontal rules.

        Args:
            text (str): The input text to be split into chunks.

        Returns:
            List[Document]: A list of `Document` objects representing the structured
            chunks of the input text. If `return_each_line` is enabled, each line
            is returned as a separate `Document`.
        """
        # Reset the state for each new file processed
        self.chunks.clear()
        self.current_chunk = Document(page_content="")
        self.current_header_stack.clear()

        raw_lines = text.splitlines(keepends=True)

        while raw_lines:
            raw_line = raw_lines.pop(0)
            header_match = self._match_header(raw_line)
            code_match = self._match_code(raw_line)
            horz_match = self._match_horz(raw_line)
            if header_match:
                self._complete_chunk_doc()

                if not self.strip_headers:
                    self.current_chunk.page_content += raw_line

                # add the header to the stack
                header_depth = len(header_match.group(1))
                header_text = header_match.group(2)
                self._resolve_header_stack(header_depth, header_text)
            elif code_match:
                self._complete_chunk_doc()
                self.current_chunk.page_content = self._resolve_code_chunk(
                    raw_line, raw_lines
                )
                self.current_chunk.metadata["Code"] = code_match.group(1)
                self._complete_chunk_doc()
            elif horz_match:
                self._complete_chunk_doc()
            else:
                self.current_chunk.page_content += raw_line

        self._complete_chunk_doc()
        # I don't see why `return_each_line` is a necessary feature of this splitter.
        # It's easy enough to to do outside of the class and the caller can have more
        # control over it.
        if self.return_each_line:
            return [
                Document(page_content=line, metadata=chunk.metadata)
                for chunk in self.chunks
                for line in chunk.page_content.splitlines()
                if line and not line.isspace()
            ]
        return self.chunks

    def _resolve_header_stack(self, header_depth: int, header_text: str) -> None:
        for i, (depth, _) in enumerate(self.current_header_stack):
            if depth == header_depth:
                self.current_header_stack[i] = (header_depth, header_text)
                self.current_header_stack = self.current_header_stack[: i + 1]
                return
        self.current_header_stack.append((header_depth, header_text))

    def _resolve_code_chunk(self, current_line: str, raw_lines: List[str]) -> str:
        chunk = current_line
        while raw_lines:
            raw_line = raw_lines.pop(0)
            chunk += raw_line
            if self._match_code(raw_line):
                return chunk
        return ""

    def _complete_chunk_doc(self) -> None:
        chunk_content = self.current_chunk.page_content
        # Discard any empty documents
        if chunk_content and not chunk_content.isspace():
            # Apply the header stack as metadata
            for depth, value in self.current_header_stack:
                # Ensure header_key is found before assigning
                header_key = self.splittable_headers.get("#" * depth)
                if header_key:  # Only add metadata if the header level is configured
                    self.current_chunk.metadata[header_key] = value
            self.chunks.append(self.current_chunk)
        # Reset the current chunk
        self.current_chunk = Document(page_content="")

    # Match methods
    def _match_header(self, line: str) -> Union[re.Match, None]:
        match = re.match(r"^(#{1,6}) (.*)", line)
        # Only matches on the configured headers
        if match and match.group(1) in self.splittable_headers:
            return match
        return None

    def _match_code(self, line: str) -> Union[re.Match, None]:
        matches = [re.match(rule, line) for rule in [r"^```(.*)", r"^~~~(.*)"]]
        return next((match for match in matches if match), None)

    def _match_horz(self, line: str) -> Union[re.Match, None]:
        matches = [
            re.match(rule, line) for rule in [r"^\*\*\*+\n", r"^---+\n", r"^___+\n"]
        ]
        return next((match for match in matches if match), None)


class LangchainMarkdownChunker(BaseChunker):
    """
    A wrapper class for the locally defined ExperimentalMarkdownSyntaxTextSplitter
    to conform to the BaseChunker interface. This splitter splits based on
    Markdown syntax like headings, code blocks, and horizontal rules.
    """

    def __init__(
        self,
        headers_to_split_on: Union[List[Tuple[str, str]], None] = None,
        return_each_line: bool = False,
        strip_headers: bool = True,
        **kwargs,  # Allow passing other potential future args, though none are expected currently
    ):
        """
        Initializes the wrapper with an instance of the locally defined
        ExperimentalMarkdownSyntaxTextSplitter.

        Args:
            headers_to_split_on: Optional list of tuples defining header markdown (e.g., '#', '##')
                                 and the desired metadata key (e.g., 'Header 1', 'H2').
                                 If None, uses the splitter's default headers.
            return_each_line: Whether to return each line as a separate chunk. Default is False.
            strip_headers: Whether to exclude header lines from the chunk content. Default is True.
            **kwargs: Additional arguments (currently none expected for this splitter).
        """
        # Instantiate the local ExperimentalMarkdownSyntaxTextSplitter class
        self.splitter = ExperimentalMarkdownSyntaxTextSplitter(
            headers_to_split_on=headers_to_split_on,
            return_each_line=return_each_line,
            strip_headers=strip_headers,
            # **kwargs # Pass any extra args if the underlying splitter adds more later
        )
        # Store config for potential debugging or logging
        self.config: Dict[str, Any] = {
            "headers_to_split_on": headers_to_split_on,
            "return_each_line": return_each_line,
            "strip_headers": strip_headers,
            **kwargs,
        }
        # Use class name in log for clarity
        print(f"Initialized {self.__class__.__name__} with config: {self.config}")

    def split_text(self, text: str) -> List[str]:
        """
        Splits the text using the underlying ExperimentalMarkdownSyntaxTextSplitter
        and returns the page content of each resulting Document.

        Args:
            text: The markdown text to split.

        Returns:
            A list of text chunks (strings).
        """
        print(f"{self.__class__.__name__} splitting text (length: {len(text)} chars)")

        # ExperimentalMarkdownSyntaxTextSplitter returns List[Document]
        # We need to extract the page_content to match the BaseChunker interface (List[str])
        documents: List[Document] = self.splitter.split_text(text)

        # Extract page_content from each document
        chunks: List[str] = [doc.page_content for doc in documents]

        print(f"{self.__class__.__name__} produced {len(chunks)} chunks")
        return chunks

    def __repr__(self):
        # Updated representation string to reflect using the local class
        return f"{self.__class__.__name__}(splitter=ExperimentalMarkdownSyntaxTextSplitter, config={self.config})"
