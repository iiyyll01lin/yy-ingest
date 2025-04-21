import sys
import multiprocessing
import os
import logging  # Import logging

# Set up basic logging configuration if not already done elsewhere
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
from chunker.chunking.langchain_markdown_chunker import LangchainMarkdownChunker
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
            logging.warning(f"Could not determine device from model parameters: {e}")
            self.device_type = "cuda" if torch.cuda.is_available() else "cpu"

        # Enable mixed precision if on CUDA
        self.use_amp = self.device_type == "cuda" and torch.cuda.is_available()

        if self.use_amp:
            logging.info(f"Mixed precision enabled for {self.device_type}")
        else:
            logging.info(f"Using standard precision on {self.device_type}")

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
                        logging.warning(
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
                    logging.warning(
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

    logging.info(f"Creating embedding function with device: {device}")

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


def create_chunker(chunker_type: ChunkMethod, **kwargs) -> BaseChunker:
    """Create a chunker of the specified type with the given parameters.

    Args:
        chunker_type: Type of chunker (Enum member from ChunkMethod)
        **kwargs: Additional parameters for the chunker

    Returns:
        A configured chunker instance conforming to BaseChunker interface
    """
    ef = kwargs.pop("embedding_function", None)
    logging.info(f"Creating chunker of type: {chunker_type} with kwargs: {kwargs}")

    if chunker_type == ChunkMethod.RECURSIVE_TOKEN:
        return RecursiveTokenChunker(
            chunk_size=kwargs.get("chunk_size", 2100),
            chunk_overlap=kwargs.get("chunk_overlap", 1700),
            length_function=openai_token_count,
        )
    elif chunker_type == ChunkMethod.FIXED_TOKEN:
        return FixedTokenChunker(
            chunk_size=kwargs.get("chunk_size", 2100),
            chunk_overlap=kwargs.get("chunk_overlap", 1700),
            encoding_name=kwargs.get("encoding_name", "cl100k_base"),
        )
    elif chunker_type == ChunkMethod.KAMRADT:
        if ef is None:
            logging.error(
                "embedding_function is required for Kamradt chunker but was not provided."
            )
            raise ValueError("embedding_function is required for Kamradt chunker")
        return KamradtModifiedChunker(
            avg_chunk_size=kwargs.get("avg_chunk_size", 2100), embedding_function=ef
        )
    elif chunker_type == ChunkMethod.CLUSTER_SEMANTIC:
        if ef is None:
            logging.error(
                "embedding_function is required for ClusterSemantic chunker but was not provided."
            )
            raise ValueError(
                "embedding_function is required for ClusterSemantic chunker"
            )
        return ClusterSemanticChunker(
            embedding_function=ef,
            max_chunk_size=kwargs.get("max_chunk_size", 5100),
            length_function=openai_token_count,
        )
    elif chunker_type == ChunkMethod.LANGCHAIN_MARKDOWN:
        return LangchainMarkdownChunker(
            headers_to_split_on=kwargs.get("headers_to_split_on", None),
            return_each_line=kwargs.get("return_each_line", False),
            strip_headers=kwargs.get("strip_headers", False),
        )
    # TODO: uncomment when ready
    # elif chunker_type == ChunkMethod.LLM_SEMANTIC:
    #     return LLMSemanticChunker(
    #         organisation=kwargs.get("organisation", "openai"),
    #         model_name=kwargs.get("model_name", "gpt-4o"),
    #         api_key=kwargs.get("api_key"),
    #     )
    else:
        # This should ideally not happen since using Enums correctly upstream
        logging.error(f"Unknown or unsupported chunker type received: {chunker_type}")
        raise ValueError(f"Unknown or unsupported chunker type: {chunker_type}")


def run_chunker_on_directory(
    chunker: BaseChunker,
    input_dir: str = "chunker/test_data/",
    output_dir: Optional[str] = None,  # Keep output_dir for potential future use
    original_pdf_name: str = "",
) -> List[Dict[str, Any]]:
    """Run a chunker on markdown files in a directory.

    Args:
        chunker: The chunker to use
        input_dir: Directory containing markdown files to chunk
        output_dir: Directory to save output JSON files (defaults to input_dir if None) - currently unused for saving
        original_pdf_name: Original name of the source PDF

    Returns:
        The chunking results as a list of dictionaries, or None if an error occurs.
    """
    runner = BaseChunkerRunner(
        markdown_dir=input_dir, original_pdf_name=original_pdf_name
    )
    chunker_name = chunker.__class__.__name__
    logging.info(
        f"[{chunker_name}] Starting chunking process for directory: {input_dir}"
    )

    try:
        logging.info(f"[{chunker_name}] Calling runner.run...")
        json_output = runner.run(chunker)
        logging.info(
            f"[{chunker_name}] runner.run completed. Result type: {type(json_output)}, Length (if list): {len(json_output) if isinstance(json_output, list) else 'N/A'}"
        )

        # Optional: Add detailed logging of the first few chunks if needed for debugging
        # if isinstance(json_output, list) and len(json_output) > 0:
        #     logging.debug(f"[{chunker_name}] First chunk example: {json_output[0]}")

        # uncomment this to save to file separately
        # if output_dir is None:
        #     output_dir = "/app/api/yy_chunker/chunker/test_data/temp_output"
        # os.makedirs(output_dir, exist_ok=True)
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # output_filename = f"{output_dir}/output_{chunker_name}_{timestamp}.json"
        # try:
        #     with open(output_filename, "w") as f:
        #         json.dump(
        #             json_output,
        #             f,
        #             indent=4,
        #             default=lambda o: str(o) if not isinstance(o, (dict, list, str, int, float, bool, type(None))) else o
        #         )
        #     logging.info(f"[{chunker_name}] Output saved to {output_filename}")
        # except Exception as save_exc:
        #     logging.error(f"[{chunker_name}] Failed to save output to {output_filename}: {save_exc}", exc_info=True)

        return json_output

    except Exception as e:
        logging.error(
            f"[{chunker_name}] Error during chunking: {str(e)}", exc_info=True
        )
        # Return None or an empty list to indicate failure clearly
        return None


# Define the worker function outside of batch_run_chunkers to make it picklable
def process_config(config, input_dir, output_dir, original_pdf_name):
    """Process a single chunker configuration.

    This function must be defined at module level (not inside another function)
    to be picklable for multiprocessing.
    """
    process_name = multiprocessing.current_process().name
    logging.info(f"[{process_name}] Worker started for config: {config}")
    try:
        # Make a copy to avoid modifying the original dict passed via multiprocessing
        config_copy = config.copy()
        chunker_type = config_copy.pop("type")
        logging.info(f"[{process_name}] Processing chunker_type: {chunker_type}")

        # Embedding function creation is handled in the main process for GPU safety
        # This worker assumes it receives a config *without* needing to create 'ef'
        if chunker_type in [ChunkMethod.KAMRADT, ChunkMethod.CLUSTER_SEMANTIC]:
            # This path should ideally not be taken if separation logic in batch_run_chunkers is correct
            logging.warning(
                f"[{process_name}] Received embedding-dependent config {chunker_type} in worker process. This might cause issues."
            )
            # Attempt to create on CPU as a fallback, but this indicates a logic issue upstream
            try:
                ef = create_embedding_function(device="cpu")
                config_copy["embedding_function"] = ef
            except Exception as e:
                logging.error(
                    f"[{process_name}] Failed to create fallback CPU embedding function for {chunker_type}: {e}",
                    exc_info=True,
                )
                return (
                    None,
                    None,
                    (
                        config,
                        f"Failed to create fallback CPU embedding function: {str(e)}",
                        traceback.format_exc(),
                    ),
                )

        logging.info(
            f"[{process_name}] Creating chunker {chunker_type} with config: {config_copy}"
        )
        chunker = create_chunker(chunker_type, **config_copy)
        logging.info(
            f"[{process_name}] Running chunker {chunker.__class__.__name__} on directory {input_dir}"
        )
        result = run_chunker_on_directory(
            chunker, input_dir, output_dir, original_pdf_name
        )

        chunker_class_name = chunker.__class__.__name__
        logging.info(
            f"[{process_name}] Completed processing with {chunker_class_name}. Result type: {type(result)}"
        )
        # Return None for result if run_chunker_on_directory failed
        return chunker_class_name, result, None
    except Exception as exc:
        tb = traceback.format_exc()
        logging.error(
            f"[{process_name}] Unhandled exception processing config {config}: {exc}",
            exc_info=True,
        )
        return None, None, (config, str(exc), tb)


def batch_run_chunkers(
    chunker_configs: List[Dict[str, Any]],
    input_dir: str = "chunker/test_data/",
    output_dir: Optional[str] = None,
    original_pdf_name: str = "",
    max_workers: Optional[int] = None,
) -> tuple[Optional[List[List[Dict[str, Any]]]], Optional[List[str]]]:
    """Run multiple chunkers in parallel on the same input directory.

    Returns:
        A tuple containing:
        - List of chunking results (each item is the result from one chunker, or None if failed)
        - List of chunker class names (in the same order as the results)
        Returns (None, None) if a critical error occurs during setup.
    """
    logging.info(
        f"[batch_run_chunkers] Starting batch processing. Input dir: {input_dir}, PDF: {original_pdf_name}"
    )
    logging.info(
        f"[batch_run_chunkers] Received {len(chunker_configs)} chunker configurations: {chunker_configs}"
    )

    if output_dir is None:
        output_dir = "/app/api/yy_chunker/chunker/test_data/temp_output"
        logging.info(
            f"[batch_run_chunkers] Defaulting output directory to: {output_dir}"
        )

    # yy: since we do not have multiple chunker output, just return list
    results = []
    chunker_class_names = []
    errors = []  # Collect error messages for logging at the end

    # Separate configs by whether they need embedding
    needs_embedding = []
    no_embedding = []

    logging.info(
        "[batch_run_chunkers] Separating configurations based on embedding requirement..."
    )
    for config in chunker_configs:
        try:
            config_type = config.get("type")  # Use .get for safety
            if config_type is None:
                logging.warning(
                    f"[batch_run_chunkers] Config missing 'type': {config}. Skipping."
                )
                errors.append(f"Config missing 'type': {config}")
                continue

            # Check against Enum members
            if config_type in [ChunkMethod.KAMRADT, ChunkMethod.CLUSTER_SEMANTIC]:
                needs_embedding.append(config)
                logging.info(
                    f"[batch_run_chunkers] Config needs embedding (main process): {config}"
                )
            elif config_type in [
                ChunkMethod.FIXED_TOKEN,
                ChunkMethod.RECURSIVE_TOKEN,
                ChunkMethod.LANGCHAIN_MARKDOWN,
            ]:
                no_embedding.append(config)
                logging.info(
                    f"[batch_run_chunkers] Config needs no embedding (parallel process): {config}"
                )
            else:
                # Handle unknown types or types needing embedding but not listed
                logging.warning(
                    f"[batch_run_chunkers] Uncategorized chunker type '{config_type}' found in config: {config}. Assuming no embedding needed."
                )
                # Decide whether to add to needs_embedding or handle differently
                no_embedding.append(
                    config
                )  # Defaulting to no_embedding for safety/simplicity
        except Exception as e:
            logging.error(
                f"[batch_run_chunkers] Error processing config during separation: {config} - {e}",
                exc_info=True,
            )
            errors.append(f"Error separating config {config}: {e}")

    # Process configs that need embedding first in the main process
    if needs_embedding:
        logging.info(
            f"[batch_run_chunkers] Processing {len(needs_embedding)} configs requiring embedding in the main process..."
        )
        ef = None  # Initialize ef outside the loop
        try:
            # Create embedding function once in the main process
            logging.info(
                "[batch_run_chunkers] Creating embedding function for main process (trying CUDA)..."
            )
            # Attempt CUDA first, fallback to CPU if needed or specified
            ef_device = "cuda" if torch.cuda.is_available() else "cpu"
            ef = create_embedding_function(device=ef_device)
            logging.info(
                f"[batch_run_chunkers] Embedding function created successfully on device: {ef_device}"
            )

            for config in needs_embedding:
                try:
                    # Make a copy to avoid modifying the original list item
                    config_copy = config.copy()
                    chunker_type = config_copy.pop(
                        "type"
                    )  # Remove type before passing to create_chunker
                    logging.info(
                        f"[batch_run_chunkers] Main Process: Processing {chunker_type} with config: {config_copy}"
                    )

                    config_copy["embedding_function"] = (
                        ef  # Add the created embedding function
                    )
                    chunker = create_chunker(chunker_type, **config_copy)

                    logging.info(
                        f"[batch_run_chunkers] Main Process: Running chunker {chunker.__class__.__name__}..."
                    )
                    result = run_chunker_on_directory(
                        chunker, input_dir, output_dir, original_pdf_name
                    )
                    chunker_class_name = chunker.__class__.__name__

                    # Check if run_chunker_on_directory returned None (indicating failure)
                    if result is None:
                        logging.error(
                            f"[batch_run_chunkers] Main Process: Chunker {chunker_class_name} failed (returned None). Config: {config}"
                        )
                        errors.append(
                            f"Chunker {chunker_class_name} failed in main process. Config: {config}"
                        )
                        # Append None to results to maintain order, or handle as needed
                        results.append(None)
                        chunker_class_names.append(chunker_class_name)
                    else:
                        # yy: modify to not adding chunker name as key
                        results.append(result)
                        chunker_class_names.append(chunker_class_name)
                        logging.info(
                            f"[batch_run_chunkers] Main Process: Completed processing with {chunker_class_name}. Result length: {len(result) if isinstance(result, list) else 'N/A'}"
                        )

                except Exception as exc:
                    error_msg = f"[batch_run_chunkers] Main Process: Error processing {config}: {exc}"
                    logging.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    # Append None if this specific config failed, maintain order
                    results.append(None)
                    chunker_class_names.append(
                        config.get("type", "UnknownType") + "_Error"
                    )  # Placeholder name

        except Exception as e:
            # Critical error creating the main embedding function
            error_msg = f"[batch_run_chunkers] CRITICAL: Failed to create main embedding function: {str(e)}"
            logging.error(error_msg, exc_info=True)
            errors.append(error_msg)
            # Optionally, decide if processing should stop entirely
            # return None, None # Indicate critical failure

    # Process configs that don't need embedding in parallel
    if no_embedding:
        logging.info(
            f"[batch_run_chunkers] Processing {len(no_embedding)} configs without embedding requirement using parallel processes..."
        )
        # Determine optimal number of workers if not specified
        if max_workers is None:
            # Use a reasonable default based on available CPUs
            cpu_count = multiprocessing.cpu_count()
            max_workers = max(
                1, cpu_count - 1 if cpu_count > 1 else 1
            )  # Ensure at least 1 worker
            logging.info(
                f"[batch_run_chunkers] Auto-detected {max_workers} worker processes (CPU count: {cpu_count})"
            )
        else:
            logging.info(
                f"[batch_run_chunkers] Using specified max_workers: {max_workers}"
            )

        # Process configs in parallel using ProcessPoolExecutor
        try:
            # Use 'spawn' context explicitly if needed, though set_start_method should handle it
            # context = multiprocessing.get_context("spawn")
            # with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers, mp_context=context) as executor:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers
            ) as executor:
                logging.info(
                    f"[batch_run_chunkers] ProcessPoolExecutor created with {max_workers} workers."
                )
                # Prepare the worker function with fixed arguments
                worker_fn = partial(
                    process_config,
                    input_dir=input_dir,
                    output_dir=output_dir,
                    original_pdf_name=original_pdf_name,
                )

                # Submit all configs for processing
                logging.info(
                    f"[batch_run_chunkers] Submitting {len(no_embedding)} tasks to executor..."
                )
                future_to_config = {
                    executor.submit(
                        worker_fn, config
                    ): config  # Pass the original config for error reporting
                    for config in no_embedding
                }
                logging.info(f"[batch_run_chunkers] All tasks submitted.")

                # Collect results as they complete
                logging.info(
                    "[batch_run_chunkers] Waiting for parallel tasks to complete..."
                )
                processed_count = 0
                for future in concurrent.futures.as_completed(future_to_config):
                    config = future_to_config[future]
                    processed_count += 1
                    logging.info(
                        f"[batch_run_chunkers] Task completed ({processed_count}/{len(no_embedding)}). Processing result for config: {config}"
                    )
                    try:
                        chunker_class_name, result, error_info = future.result()
                        if error_info:
                            orig_config, exc_str, tb = error_info
                            error_msg = f"[batch_run_chunkers] Worker Error processing {orig_config}: {exc_str}"
                            logging.error(error_msg)
                            logging.debug(
                                f"Worker Traceback:\n{tb}"
                            )  # Log traceback at debug level
                            errors.append(error_msg)
                            # Append None to results, placeholder name
                            results.append(None)
                            chunker_class_names.append(
                                orig_config.get("type", "UnknownType") + "_Error"
                            )
                        elif chunker_class_name is None:
                            # Handle case where worker returns None for name without error_info (shouldn't happen ideally)
                            error_msg = f"[batch_run_chunkers] Worker returned None for chunker name for config {config}. Result was: {result}"
                            logging.error(error_msg)
                            errors.append(error_msg)
                            results.append(result)  # Append result even if name is None
                            chunker_class_names.append("UnknownWorkerResult")
                        else:
                            # Success case from worker
                            # yy: modify to not adding chunker name as key
                            results.append(result)
                            chunker_class_names.append(chunker_class_name)
                            logging.info(
                                f"[batch_run_chunkers] Completed processing with {chunker_class_name} from worker. Result type: {type(result)}"
                            )
                    except Exception as exc:
                        # Exception occurred during future.result() or within the loop here
                        error_msg = f"[batch_run_chunkers] Exception retrieving result for {config}: {exc}"
                        logging.error(error_msg, exc_info=True)
                        errors.append(error_msg)
                        # Append None, placeholder name
                        results.append(None)
                        chunker_class_names.append(
                            config.get("type", "UnknownType") + "_FutureError"
                        )
        except Exception as e:
            # Error related to the ProcessPoolExecutor itself
            error_msg = f"[batch_run_chunkers] Process pool execution failed: {str(e)}"
            logging.error(error_msg, exc_info=True)
            errors.append(error_msg)
            # Depending on severity, might return None, None
            # return None, None

    # Log any errors encountered during the whole batch process
    if errors:
        logging.warning(
            f"[batch_run_chunkers] Encountered {len(errors)} errors during batch processing:"
        )
        for i, error in enumerate(errors):
            logging.warning(f"  Error {i+1}: {error}")
    else:
        logging.info(
            "[batch_run_chunkers] Batch processing completed with no reported errors."
        )

    logging.info(
        f"[batch_run_chunkers] Returning {len(results)} results and {len(chunker_class_names)} class names."
    )
    logging.debug(
        f"[batch_run_chunkers] Final results structure (first element type if exists): {type(results[0]) if results else 'N/A'}"
    )
    logging.debug(f"[batch_run_chunkers] Final class names: {chunker_class_names}")

    # Ensure the lengths match, even if results contain None
    if len(results) != len(chunker_class_names):
        logging.error(
            f"[batch_run_chunkers] Mismatch between results ({len(results)}) and class names ({len(chunker_class_names)}) count!"
        )
        # Attempt to reconcile or return error indicator? For now, just log.

    return results, chunker_class_names
