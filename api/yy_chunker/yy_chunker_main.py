import sys
import multiprocessing
import os


# Set the start method to 'spawn' to avoid CUDA initialization issues
# This needs to be called at the very beginning before any multiprocessing happens
if __name__ == "__main__" or multiprocessing.get_start_method(allow_none=True) is None:
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        # If it's already set, don't bother
        pass

# Add the yy_chunker directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from chunker.chunking import (
    FixedTokenChunker,
    RecursiveTokenChunker,
    ClusterSemanticChunker,
    LLMSemanticChunker,
    KamradtModifiedChunker,
    BaseChunker,
)
from chunker.chunker_runner import BaseChunkerRunner
from chunker.utils import openai_token_count

from api.models import ChunkMethod

from langchain_huggingface import HuggingFaceEmbeddings
from datetime import datetime
import torch
import traceback
import json
from typing import List, Dict, Any, Optional
from enum import Enum
import concurrent.futures
from functools import partial


# TODO: let user add their own embedding models
class EmbeddingModel(str, Enum):
    """Enum for supported embedding models."""

    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_DAVINCI_V3 = "text-embedding-ada-002"


class ChromaEmbeddingAdapter:
    """Adapter that converts LangChain embedding models to ChromaDB compatible interface."""

    # for Automatic Mixed Precision package

    def __init__(self, langchain_embedder):
        self.langchain_embedder = langchain_embedder

        # Cache for embeddings to avoid recomputing
        self._cache = {}

        # Determine device and check for CUDA availability
        try:
            self.device = next(langchain_embedder._client.parameters()).device
            self.device_type = self.device.type  # 'cuda' or 'cpu'
        except (AttributeError, StopIteration) as e:
            # Fallback if we can't access model parameters directly
            print(f"Could not determine device from model parameters: {e}")
            self.device_type = "cuda" if torch.cuda.is_available() else "cpu"

        # Enable mixed precision if on CUDA
        self.use_amp = self.device_type == "cuda" and torch.cuda.is_available()

        if self.use_amp:
            print(f"Mixed precision enabled for {self.device_type}")
        else:
            print(f"Using standard precision on {self.device_type}")

    def __call__(self, input):
        # ChromaDB expects __call__ with 'input' parameter

        # For batched inputs, process them all at once
        if not isinstance(input, str):
            # Use caching for batch inputs
            uncached = [x for x in input if x not in self._cache]
            if uncached:
                if self.use_amp:
                    try:
                        with torch.cuda.amp.autocast():
                            embeddings = self.langchain_embedder.embed_documents(
                                uncached
                            )
                    except Exception as e:
                        # Fall back if autocast fails
                        print(
                            f"Mixed precision failed, falling back to standard precision: {e}"
                        )
                        embeddings = self.langchain_embedder.embed_documents(uncached)
                else:
                    # Use standard precision
                    embeddings = self.langchain_embedder.embed_documents(uncached)

                # Update cache
                for i, text in enumerate(uncached):
                    self._cache[text] = embeddings[i]

            # Return all embeddings from cache
            return [self._cache[x] for x in input]
        else:
            # Single input
            if input in self._cache:
                return self._cache[input]

            if self.use_amp:
                try:
                    with torch.cuda.amp.autocast():
                        embedding = self.langchain_embedder.embed_query(input)
                except Exception as e:
                    # Fall back if autocast fails
                    print(
                        f"Mixed precision failed, falling back to standard precision: {e}"
                    )
                    embedding = self.langchain_embedder.embed_query(input)
            else:
                # Use standard precision
                embedding = self.langchain_embedder.embed_query(input)

            # Cache the result
            self._cache[input] = embedding
            return embedding


def create_embedding_function(
    model_name: str = EmbeddingModel.ALL_MINILM_L6_V2, device: str = None
) -> ChromaEmbeddingAdapter:
    """Create an embedding function compatible with chunkers.

    Args:
        model_name: Name of the HuggingFace model to use
        device: Device to run the model on (cuda, cpu, or None for auto-detection)

    Returns:
        A ChromaDB-compatible embedding function
    """
    # Auto-detect device if not specified
    if device is None:
        device = "cuda" if torch.cuda.is_available() and not is_subprocess() else "cpu"

    print(f"Creating embedding function with device: {device}")

    langchain_ef = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
    return ChromaEmbeddingAdapter(langchain_ef)


# Helper function to detect if we're in a subprocess
def is_subprocess():
    """Check if the current process is a subprocess created by multiprocessing."""
    return multiprocessing.current_process().name != "MainProcess"


def create_chunker(chunker_type: str, **kwargs) -> BaseChunker:
    """Create a chunker of the specified type with the given parameters.

    Args:
        chunker_type: Type of chunker (recursive_token, fixed_token, kamradt, cluster_semantic, llm_semantic)
        **kwargs: Additional parameters for the chunker

    Returns:
        A configured chunker instance
    """
    ef = kwargs.pop("embedding_function", None)

    if chunker_type == "recursive_token":
        return RecursiveTokenChunker(
            chunk_size=kwargs.get("chunk_size", 2100),
            chunk_overlap=kwargs.get("chunk_overlap", 1700),
            length_function=openai_token_count,
        )
    elif chunker_type == "fixed_token":
        return FixedTokenChunker(
            chunk_size=kwargs.get("chunk_size", 2100),
            chunk_overlap=kwargs.get("chunk_overlap", 1700),
            encoding_name=kwargs.get("encoding_name", "cl100k_base"),
        )
    elif chunker_type == "kamradt":
        if ef is None:
            raise ValueError("embedding_function is required for Kamradt chunker")
        return KamradtModifiedChunker(
            avg_chunk_size=kwargs.get("avg_chunk_size", 2100), embedding_function=ef
        )
    elif chunker_type == "cluster_semantic":
        if ef is None:
            print("ef is None")
            raise ValueError(
                "embedding_function is required for ClusterSemantic chunker"
            )
        return ClusterSemanticChunker(
            embedding_function=ef,
            max_chunk_size=kwargs.get("max_chunk_size", 5100),
            length_function=openai_token_count,
        )
    # TODO: uncomment when ready
    # elif chunker_type == "llm_semantic":
    #     return LLMSemanticChunker(
    #         organisation=kwargs.get("organisation", "openai"),
    #         model_name=kwargs.get("model_name", "gpt-4o"),
    #         api_key=kwargs.get("api_key"),
    #     )
    else:
        print("Unknown chunker type")
        raise ValueError(f"Unknown chunker type: {chunker_type}")


def run_chunker_on_directory(
    chunker: BaseChunker,
    input_dir: str = "chunker/test_data/",
    output_dir: Optional[str] = None,
    original_pdf_name: str = "",
) -> List[Dict[str, Any]]:
    """Run a chunker on markdown files in a directory.

    Args:
        chunker: The chunker to use
        input_dir: Directory containing markdown files to chunk
        output_dir: Directory to save output JSON files (defaults to input_dir if None)

    Returns:
        The chunking results as a list of dictionaries
    """
    runner = BaseChunkerRunner(
        markdown_dir=input_dir, original_pdf_name=original_pdf_name
    )

    try:
        print(f"Chunking with {chunker.__class__.__name__}")
        json_output = runner.run(chunker)

        # uncomment this to save to file separately
        # if output_dir is None:
        #     output_dir = "/app/api/yy_chunker/chunker/test_data/temp_output"

        # os.makedirs(output_dir, exist_ok=True)

        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # output_filename = (
        #     f"{output_dir}/output_{chunker.__class__.__name__}_{timestamp}.json"
        # )

        # with open(output_filename, "w") as f:
        #     json.dump(
        #         json_output,
        #         f,
        #         indent=4,
        #         default=lambda o: (
        #             str(o)
        #             if not isinstance(
        #                 o, (dict, list, str, int, float, bool, type(None))
        #             )
        #             else o
        #         ),
        #     )

        # print(f"Output saved to {output_filename}")
        return json_output

    except Exception as e:
        print(f"Error chunking with {chunker.__class__.__name__}: {str(e)}")
        return []


# Define the worker function outside of batch_run_chunkers to make it picklable
def process_config(config, input_dir, output_dir, original_pdf_name):
    """Process a single chunker configuration.

    This function must be defined at module level (not inside another function)
    to be picklable for multiprocessing.
    """
    try:
        chunker_type = config.pop("type")
        print(f"[process_config] Processing chunker_type: {chunker_type}")

        # Create a copy to avoid modifying the original
        config_copy = config.copy()

        # in the batch_run_chunkers, will not use process_config with the methods needs
        # embedding models, aka will not use multi-process for those methods.
        # Create embedding function if needed for this chunker type
        if chunker_type in [ChunkMethod.KAMRADT, ChunkMethod.CLUSTER_SEMANTIC]:
            try:
                # Force CPU for subprocess embedding to avoid CUDA initialization issues
                ef = create_embedding_function(device="cpu")
                config_copy["embedding_function"] = ef
            except Exception as e:
                return (
                    None,
                    None,
                    (
                        config,
                        f"Failed to create embedding function: {str(e)}",
                        traceback.format_exc(),
                    ),
                )

        chunker = create_chunker(chunker_type, **config_copy)
        result = run_chunker_on_directory(
            chunker, input_dir, output_dir, original_pdf_name
        )

        chunker_class_name = chunker.__class__.__name__
        return chunker_class_name, result, None
    except Exception as exc:
        tb = traceback.format_exc()
        return None, None, (config, str(exc), tb)


def batch_run_chunkers(
    chunker_configs: List[Dict[str, Any]],
    input_dir: str = "chunker/test_data/",
    output_dir: Optional[str] = None,
    original_pdf_name: str = "",
    max_workers: Optional[int] = None,
) -> tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
    """Run multiple chunkers in parallel on the same input directory."""
    if output_dir is None:
        output_dir = "/app/api/yy_chunker/chunker/test_data/temp_output"

    results = {}
    chunker_class_names = []
    errors = []

    # Separate configs by whether they need embedding
    needs_embedding = []
    no_embedding = []

    for config in chunker_configs:
        if config["type"] in [ChunkMethod.KAMRADT, ChunkMethod.CLUSTER_SEMANTIC]:
            needs_embedding.append(config)
        else:
            no_embedding.append(config)

    # Process configs that need embedding first in the main process
    if needs_embedding:
        try:
            # Create embedding function once in the main process
            ef = create_embedding_function(device="cuda")  # Use GPU in main process

            for config in needs_embedding:
                try:
                    chunker_type = config["type"]
                    print(
                        f"[batch_run_chunkers] Processing in main process: {chunker_type}"
                    )

                    # Create a copy to avoid modifying the original
                    config_copy = config.copy()
                    if "type" in config_copy:
                        config_copy.pop("type")

                    config_copy["embedding_function"] = ef
                    chunker = create_chunker(chunker_type, **config_copy)

                    result = run_chunker_on_directory(
                        chunker, input_dir, output_dir, original_pdf_name
                    )

                    chunker_class_name = chunker.__class__.__name__
                    chunker_class_names.append(chunker_class_name)
                    results[chunker_class_name] = result
                    print(f"Completed processing with {chunker_class_name}")
                except Exception as exc:
                    error_msg = f"Error processing {config} in main process: {exc}"
                    print(f"ERROR: {error_msg}")
                    errors.append(error_msg)
                    print(traceback.format_exc())
        except Exception as e:
            error_msg = f"Failed to create embedding function in main process: {str(e)}"
            print(f"ERROR: {error_msg}")
            errors.append(error_msg)
            print(traceback.format_exc())

    # Process configs that don't need embedding in parallel
    if no_embedding:
        # Determine optimal number of workers if not specified
        if max_workers is None:
            # Use a reasonable default based on available CPUs
            max_workers = max(1, multiprocessing.cpu_count() - 1)  # Leave one CPU free
            print(f"Auto-detected {max_workers} worker processes")

        # Process configs in parallel using ProcessPoolExecutor
        try:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers
            ) as executor:
                # Prepare the worker function with fixed arguments
                worker_fn = partial(
                    process_config,
                    input_dir=input_dir,
                    output_dir=output_dir,
                    original_pdf_name=original_pdf_name,
                )

                # Submit all configs for processing
                future_to_config = {
                    executor.submit(worker_fn, config.copy()): config
                    for config in no_embedding
                }

                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_config):
                    try:
                        chunker_class_name, result, error_info = future.result()
                        if error_info:
                            config, exc_str, tb = error_info
                            error_msg = f"Error processing {config}: {exc_str}"
                            print(f"ERROR: {error_msg}")
                            print(tb)
                            errors.append(error_msg)
                        else:
                            chunker_class_names.append(chunker_class_name)
                            results[chunker_class_name] = result
                            print(f"Completed processing with {chunker_class_name}")
                    except Exception as exc:
                        config = future_to_config[future]
                        error_msg = f"Future for {config} raised exception: {exc}"
                        print(f"ERROR: {error_msg}")
                        errors.append(error_msg)
                        print(traceback.format_exc())
        except Exception as e:
            error_msg = f"Process pool execution failed: {str(e)}"
            print(f"ERROR: {error_msg}")
            errors.append(error_msg)
            print(traceback.format_exc())

    # Log any errors encountered
    if errors:
        print(f"[batch_run_chunkers] Encountered {len(errors)} errors:")
        for i, error in enumerate(errors):
            print(f"  Error {i+1}: {error}")

    return results, chunker_class_names
