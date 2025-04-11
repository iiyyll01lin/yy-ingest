# This script is adapted from the LangChain package, developed by LangChain AI, all credits to them.
# Original code can be found at: https://github.com/langchain-ai/langchain/blob/master/libs/text-splitters/langchain_text_splitters/base.py
# License: MIT License

from abc import ABC, abstractmethod
from enum import Enum
import logging
import re
from typing import (
    AbstractSet,
    Any,
    Callable,
    Collection,
    Iterable,
    List,
    Literal,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)
from .base_chunker import BaseChunker


from attr import dataclass

logger = logging.getLogger(__name__)

TS = TypeVar("TS", bound="TextSplitter")


class TextSplitter(BaseChunker, ABC):
    """Interface for splitting text into chunks."""

    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
        keep_separator: bool = False,
        add_start_index: bool = False,
        strip_whitespace: bool = True,
    ) -> None:
        """Create a new TextSplitter.

        Args:
            chunk_size: Maximum size of chunks to return
            chunk_overlap: Overlap in characters between chunks
            length_function: Function that measures the length of given chunks
            keep_separator: Whether to keep the separator in the chunks
            add_start_index: If `True`, includes chunk's start index in metadata
            strip_whitespace: If `True`, strips whitespace from the start and end of
                              every document
        """
        if chunk_overlap > chunk_size:
            raise ValueError(
                f"Got a larger chunk overlap ({chunk_overlap}) than chunk size "
                f"({chunk_size}), should be smaller."
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = length_function
        self._keep_separator = keep_separator
        self._add_start_index = add_start_index
        self._strip_whitespace = strip_whitespace

    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        """Split text into multiple components."""

    # def _join_docs(self, docs: List[str], separator: str) -> Optional[str]:
    #     """Join multiple docs with the provided separator."""
    #     if not docs:
    #         return None

    #     # Custom logic to handle image tags
    #     if len(docs) == 1:
    #         return docs[0]

    #     # First process each document to trim whitespace that might cause problems
    #     processed_docs = []
    #     for i, doc in enumerate(docs):
    #         # For special cases like <img and src=, trim whitespace
    #         if doc.strip() == "<img" or doc.strip().startswith("src="):
    #             processed_docs.append(doc.strip())
    #         else:
    #             processed_docs.append(doc)

    #     # Build the joined text with special handling for image tags
    #     result = processed_docs[0]
    #     for i in range(1, len(processed_docs)):
    #         curr = processed_docs[i]
    #         prev = result

    #         # Handle the case where we have "<img" and need to join with "src="
    #         if prev.endswith("<img") and (curr.startswith("src=") or curr == "src="):
    #             # Ensure exactly one space between <img and src=
    #             result = result + " " + curr

    #         # Check if we're in the middle of an image tag or URL
    #         elif ("<img" in prev and ">" not in prev) or \
    #         ("src=" in prev and '"' not in prev.split("src=")[-1]) or \
    #         ((curr.startswith("http") or ".jpg" in curr or ".png" in curr) and \
    #         (prev.endswith('src="') or prev.endswith("src="))):
    #             # Join without separator for image tags and URLs
    #             result += curr
    #         else:
    #             # Use normal separator
    #             result += separator + curr

    #     # Apply multiple regex passes to fix various spacing issues

    #     # Fix double spaces between <img and src=
    #     result = re.sub(r'<img\s+src=', '<img src=', result)

    #     # Fix missing space between <img and src=
    #     result = re.sub(r'<imgsrc=', '<img src=', result)

    #     # Fix any other irregular spacing in img tags
    #     result = re.sub(r'<img\s{2,}src=', '<img src=', result)

    #     return result

    def _join_docs(self, docs: List[str], separator: str) -> Optional[str]:
        text = separator.join(docs)
        if self._strip_whitespace:
            text = text.strip()
        if text == "":
            return None
        else:
            return text

    # def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
    #     """Merge splits into chunks according to specified parameters."""
    #     # Modified to handle image tags intelligently
    #     separator_len = self._length_function(separator)

    #     docs = []
    #     current_doc: List[str] = []
    #     total = 0

    #     i = 0
    #     while i < len(splits):
    #         split = splits[i]
    #         len_split = self._length_function(split)

    #         # Skip adding separator if we're in the middle of an image tag with URL
    #         in_img_tag = False
    #         if i > 0 and current_doc:
    #             prev_text = current_doc[-1]
    #             # Check if we're in an image tag
    #             if ("<img" in prev_text and ">" not in prev_text) or \
    #             "src=" in prev_text and '"' not in prev_text.split("src=")[-1]:
    #                 in_img_tag = True
    #             # Check if this split continues an image URL
    #             elif (split.startswith("http") or ".jpg" in split or ".png" in split) and \
    #                 (prev_text.endswith("src=") or prev_text.endswith('src="')):
    #                 in_img_tag = True

    #         # If we're not in an image tag and the combined length exceeds our limit,
    #         # finalize the current document
    #         if not in_img_tag and total + len_split + (separator_len if current_doc else 0) > self._chunk_size:
    #             if total > self._chunk_size:
    #                 logger.warning(
    #                     f"Created a chunk of size {total}, "
    #                     f"which is longer than the specified {self._chunk_size}"
    #                 )
    #             if current_doc:
    #                 doc = self._join_docs(current_doc, separator)
    #                 if doc is not None:
    #                     docs.append(doc)
    #                 # Keep on popping if:
    #                 # - we have a larger chunk than in the chunk overlap
    #                 # - or if we still have any chunks and the length is long
    #                 while total > self._chunk_overlap or (
    #                     total + len_split + (separator_len if current_doc else 0)
    #                     > self._chunk_size
    #                     and total > 0
    #                 ):
    #                     total -= self._length_function(current_doc[0])
    #                     current_doc = current_doc[1:]

    #         # Add the split to the current document
    #         current_doc.append(split)
    #         total += len_split

    #         # Increment the counter
    #         i += 1

    #     # Add any remaining document
    #     if current_doc:
    #         doc = self._join_docs(current_doc, separator)
    #         if doc is not None:
    #             docs.append(doc)
    #     return docs

    def _merge_splits(self, splits: Iterable[str], separator: str) -> List[str]:
        # We now want to combine these smaller pieces into medium size
        # chunks to send to the LLM.
        separator_len = self._length_function(separator)

        docs = []
        current_doc: List[str] = []
        total = 0
        for d in splits:
            _len = self._length_function(d)
            if (
                total + _len + (separator_len if len(current_doc) > 0 else 0)
                > self._chunk_size
            ):
                if total > self._chunk_size:
                    logger.warning(
                        f"Created a chunk of size {total}, "
                        f"which is longer than the specified {self._chunk_size}"
                    )
                if len(current_doc) > 0:
                    doc = self._join_docs(current_doc, separator)
                    if doc is not None:
                        docs.append(doc)
                    # Keep on popping if:
                    # - we have a larger chunk than in the chunk overlap
                    # - or if we still have any chunks and the length is long
                    while total > self._chunk_overlap or (
                        total + _len + (separator_len if len(current_doc) > 0 else 0)
                        > self._chunk_size
                        and total > 0
                    ):
                        total -= self._length_function(current_doc[0]) + (
                            separator_len if len(current_doc) > 1 else 0
                        )
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += _len + (separator_len if len(current_doc) > 1 else 0)
        doc = self._join_docs(current_doc, separator)
        if doc is not None:
            docs.append(doc)
        return docs

    # @classmethod
    # def from_huggingface_tokenizer(cls, tokenizer: Any, **kwargs: Any) -> TextSplitter:
    #     """Text splitter that uses HuggingFace tokenizer to count length."""
    #     try:
    #         from transformers import PreTrainedTokenizerBase

    #         if not isinstance(tokenizer, PreTrainedTokenizerBase):
    #             raise ValueError(
    #                 "Tokenizer received was not an instance of PreTrainedTokenizerBase"
    #             )

    #         def _huggingface_tokenizer_length(text: str) -> int:
    #             return len(tokenizer.encode(text))

    #     except ImportError:
    #         raise ValueError(
    #             "Could not import transformers python package. "
    #             "Please install it with `pip install transformers`."
    #         )
    #     return cls(length_function=_huggingface_tokenizer_length, **kwargs)

    @classmethod
    def from_tiktoken_encoder(
        cls: Type[TS],
        encoding_name: str = "gpt2",
        model_name: Optional[str] = None,
        allowed_special: Union[Literal["all"], AbstractSet[str]] = set(),
        disallowed_special: Union[Literal["all"], Collection[str]] = "all",
        **kwargs: Any,
    ) -> TS:
        """Text splitter that uses tiktoken encoder to count length."""
        try:
            import tiktoken
        except ImportError:
            raise ImportError(
                "Could not import tiktoken python package. "
                "This is needed in order to calculate max_tokens_for_prompt. "
                "Please install it with `pip install tiktoken`."
            )

        if model_name is not None:
            enc = tiktoken.encoding_for_model(model_name)
        else:
            enc = tiktoken.get_encoding(encoding_name)

        def _tiktoken_encoder(text: str) -> int:
            return len(
                enc.encode(
                    text,
                    allowed_special=allowed_special,
                    disallowed_special=disallowed_special,
                )
            )

        if issubclass(cls, FixedTokenChunker):
            extra_kwargs = {
                "encoding_name": encoding_name,
                "model_name": model_name,
                "allowed_special": allowed_special,
                "disallowed_special": disallowed_special,
            }
            kwargs = {**kwargs, **extra_kwargs}

        return cls(length_function=_tiktoken_encoder, **kwargs)


class FixedTokenChunker(TextSplitter):
    """Splitting text to tokens using model tokenizer."""

    def __init__(
        self,
        encoding_name: str = "cl100k_base",
        model_name: Optional[str] = None,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        allowed_special: Union[Literal["all"], AbstractSet[str]] = set(),
        disallowed_special: Union[Literal["all"], Collection[str]] = "all",
        **kwargs: Any,
    ) -> None:
        """Create a new TextSplitter."""
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
        try:
            import tiktoken
        except ImportError:
            raise ImportError(
                "Could not import tiktoken python package. "
                "This is needed in order to for FixedTokenChunker. "
                "Please install it with `pip install tiktoken`."
            )

        if model_name is not None:
            enc = tiktoken.encoding_for_model(model_name)
        else:
            enc = tiktoken.get_encoding(encoding_name)
        self._tokenizer = enc
        self._allowed_special = allowed_special
        self._disallowed_special = disallowed_special

    def split_text(self, text: str) -> List[str]:
        def _encode(_text: str) -> List[int]:
            return self._tokenizer.encode(
                _text,
                allowed_special=self._allowed_special,
                disallowed_special=self._disallowed_special,
            )

        tokenizer = Tokenizer(
            chunk_overlap=self._chunk_overlap,
            tokens_per_chunk=self._chunk_size,
            decode=self._tokenizer.decode,
            encode=_encode,
        )

        return split_text_on_tokens(text=text, tokenizer=tokenizer)


@dataclass(frozen=True)
class Tokenizer:
    """Tokenizer data class."""

    chunk_overlap: int
    """Overlap in tokens between chunks"""
    tokens_per_chunk: int
    """Maximum number of tokens per chunk"""
    decode: Callable[[List[int]], str]
    """ Function to decode a list of token ids to a string"""
    encode: Callable[[str], List[int]]
    """ Function to encode a string to a list of token ids"""


def split_text_on_tokens(*, text: str, tokenizer: Tokenizer) -> List[str]:
    """Split incoming text and return chunks using tokenizer."""
    splits: List[str] = []
    input_ids = tokenizer.encode(text)
    start_idx = 0
    cur_idx = min(start_idx + tokenizer.tokens_per_chunk, len(input_ids))
    chunk_ids = input_ids[start_idx:cur_idx]
    while start_idx < len(input_ids):
        splits.append(tokenizer.decode(chunk_ids))
        if cur_idx == len(input_ids):
            break
        start_idx += tokenizer.tokens_per_chunk - tokenizer.chunk_overlap
        cur_idx = min(start_idx + tokenizer.tokens_per_chunk, len(input_ids))
        chunk_ids = input_ids[start_idx:cur_idx]
    return splits
