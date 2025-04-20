import os
import shutil
import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Union
import logging
import tempfile
from functools import partial
import httpx
import base64

from api.config import UPLOAD_URL, SEMAPHORE
from api.pdf_processor import (
    download_pdf,
    extract_pdf,
    process_md,
    read_file,
    gen_img_desc,
)
from api.config import TASKS
from api.models import ChunkMethod, EncodingMethod
from api.yy_chunker.yy_chunker_main import batch_run_chunkers


async def task_runner(
    task_id: str,
    url: str,
    start_page: int = 1,
    end_page: int = 1,
    chunk_max_size: int = 5100,
    chunk_method: List[ChunkMethod] = [ChunkMethod.CLUSTER_SEMANTIC],
    chunk_size: int = 2100,
    chunk_overlap: int = 1700,
    avg_chunk_size: int = 5100,
    encoding_name: EncodingMethod = EncodingMethod.CL100K_BASE,
    # Parameters for LANGCHAIN_MARKDOWN
    headers_to_split_on: Optional[List[Tuple[str, str]]] = None,
    return_each_line: bool = False,
    strip_headers: bool = True,
    # **kwargs # capture extra?
):
    try:
        start_time_total = time.time()
        TASKS[task_id]["status"] = "extracting"
        # TASKS[task_id]["progress"] = 0
        # TASKS[task_id]["current_step"] = "initializing"

        # Add initial estimated time as unknown
        # TASKS[task_id]["estimated_remaining"] = None

        async with SEMAPHORE:
            # Extraction phase
            # TASKS[task_id]["current_step"] = "extracting"
            # TASKS[task_id]["progress"] = 10

            # update_time_estimate(task_id, start_time_total)

            start_time_extract = time.time()
            logging.info("[task_runner] Starting extracting process...")

            # Download and extract PDF
            # pdf_bytes = await download_pdf(url)
            pdf_extensions = ["pdf"]
            office_extensions = ["ppt", "pptx", "doc", "docx"]
            file_extension = re.search(r"\.([a-zA-Z0-9]+)$", url).group(1)
            if file_extension in pdf_extensions:
                pdf_bytes = await download_pdf(url)
            elif file_extension in office_extensions:
                file_bytes = await download_pdf(url)
                temp_dir = tempfile.mkdtemp()
                with open(
                    os.path.join(temp_dir, f"temp_file.{file_extension}"), "wb"
                ) as f:
                    f.write(file_bytes)
                pdf_bytes = read_file(temp_dir)[0]
                shutil.rmtree(temp_dir)
                logging.info(f"del file:{temp_dir}")
            else:
                raise Exception("The file format does not comply with the standard")
            loop = asyncio.get_event_loop()
            md_path = await loop.run_in_executor(
                None, extract_pdf, task_id, pdf_bytes, start_page, end_page
            )
            new_md_path = await process_md(md_path, UPLOAD_URL)

            logging.info("[task_runner] Extracting process completed.")

            # TASKS[task_id]["progress"] = 40

            # update_time_estimate(task_id, start_time_total)

            extract_time = time.time() - start_time_extract
            logging.info(f"[TIMING] Extraction process took {extract_time:.2f} seconds")

            input_dir = get_directory_from_file_path(new_md_path)

            # Chunking phase
            # TASKS[task_id]["current_step"] = "chunking"
            # TASKS[task_id]["progress"] = 50

            # update_time_estimate(task_id, start_time_total)

            start_time_chunking = time.time()

            logging.info("[task_runner] Starting chunking process...")
            logging.info(f"[task_runner] task_id: {task_id}")
            logging.info(f"[task_runner] start_page: {start_page}")
            logging.info(f"[task_runner] end_page: {end_page}")
            logging.info(f"[task_runner] input_dir: {input_dir}")
            logging.info(f"[task_runner] original_pdf_name: {url}")
            logging.info(f"[task_runner] chunk_methods: {chunk_method}")
            if ChunkMethod.LANGCHAIN_MARKDOWN in chunk_method:
                logging.info(
                    f"[task_runner] headers_to_split_on: {headers_to_split_on}"
                )
                logging.info(f"[task_runner] return_each_line: {return_each_line}")
                logging.info(f"[task_runner] strip_headers: {strip_headers}")
            if any(
                m in [ChunkMethod.FIXED_TOKEN, ChunkMethod.RECURSIVE_TOKEN]
                for m in chunk_method
            ):
                logging.info(f"[task_runner] chunk_size: {chunk_size}")
                logging.info(f"[task_runner] chunk_overlap: {chunk_overlap}")
            if ChunkMethod.FIXED_TOKEN in chunk_method:
                logging.info(f"[task_runner] encoding_name: {encoding_name}")
            if ChunkMethod.KAMRADT in chunk_method:
                logging.info(f"[task_runner] avg_chunk_size: {avg_chunk_size}")
            if ChunkMethod.CLUSTER_SEMANTIC in chunk_method:
                logging.info(f"[task_runner] chunk_max_size: {chunk_max_size}")

            # Generate chunker_configs based on the chunk methods
            chunker_configs = []

            # Map each method to its required parameters
            method_param_mapping = {
                ChunkMethod.FIXED_TOKEN: {
                    "type": ChunkMethod.FIXED_TOKEN,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "encoding_name": encoding_name,
                },
                ChunkMethod.RECURSIVE_TOKEN: {
                    "type": ChunkMethod.RECURSIVE_TOKEN,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                },
                ChunkMethod.KAMRADT: {
                    "type": ChunkMethod.KAMRADT,
                    "avg_chunk_size": avg_chunk_size,
                },
                ChunkMethod.CLUSTER_SEMANTIC: {
                    "type": ChunkMethod.CLUSTER_SEMANTIC,
                    "max_chunk_size": chunk_max_size,
                },
                # Add LLM_SEMANTIC when ready
                # ChunkMethod.LLM_SEMANTIC: {
                #     "type": ChunkMethod.LLM_SEMANTIC,
                # },
                ChunkMethod.LANGCHAIN_MARKDOWN: {
                    "type": ChunkMethod.LANGCHAIN_MARKDOWN,
                    "headers_to_split_on": headers_to_split_on,
                    "return_each_line": return_each_line,
                    "strip_headers": strip_headers,
                },
            }

            # Add configurations for each selected method
            for method in chunk_method:
                if method in method_param_mapping:
                    config = method_param_mapping[method].copy()
                    chunker_configs.append(config)
                else:
                    logging.warning(f"Chunk method '{method}' not found in mapping.")

            logging.info(
                f"[task_runner] Generated {len(chunker_configs)} chunker configurations"
            )

            logging.info(f"[task_runner] chunker_configs: {chunker_configs}")
            TASKS[task_id]["status"] = "chunking"

            all_results, chunker_class_names = await loop.run_in_executor(
                None,
                partial(
                    batch_run_chunkers,
                    chunker_configs=chunker_configs,
                    input_dir=input_dir,
                    original_pdf_name=url,
                ),
            )

            # logging.info(f"[task_runner] all_results: {all_results}")
            logging.info(f"[task_runner] chunker_class_names: {chunker_class_names}")

            # Collect results from all chunkers
            output_chunks = {}
            # yy: since we do not have multiple chunker output, just return the results
            output_chunks = all_results[0]
            # for class_name in chunker_class_names:
            #     output_chunks[class_name] = all_results[class_name]

            # TASKS[task_id]["progress"] = 90

            # update_time_estimate(task_id, start_time_total)

            logging.info("[task_runner] Chunking process completed.")

            chunking_time = time.time() - start_time_chunking

            logging.info("[task_runner] Starting generate image description process...")
            start_time_description = time.time()
            TASKS[task_id]["status"] = "generate image description"
            output_chunks = await gen_img_desc(output_chunks=output_chunks)
            logging.info("[task_runner] generate image description completed.")
            description_time = time.time() - start_time_description

            # Finalizing
            # TASKS[task_id]["current_step"] = "finalizing"
            # TASKS[task_id]["progress"] = 95

            # update_time_estimate(task_id, start_time_total)

            total_time = time.time() - start_time_total
            logging.info(f"[TIMING] Total processing took {total_time:.2f} seconds")
            logging.info(
                f"[TIMING] Summary: Extract: {extract_time:.2f}s, Chunking: {chunking_time:.2f}s, Generate Image Description: {description_time:.2f}s, Total: {total_time:.2f}s"
            )

            # TASKS[task_id]["timing"] = {
            #     "extract_time": round(extract_time, 2),
            #     "chunking_time": round(chunking_time, 2),
            #     "total_time": round(total_time, 2),
            # }

            # uncomment this to save to file unified
            # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # output_dir = "/app/api/yy_chunker/chunker/test_data/temp_output"
            # os.makedirs(output_dir, exist_ok=True)
            # output_filename = f"{output_dir}/output_chunks_{timestamp}.json"

            # with open(output_filename, "w") as f:
            #     json.dump(
            #         output_chunks,
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

            # All done
            TASKS[task_id]["status"] = "success"
            # TASKS[task_id]["progress"] = 100
            # TASKS[task_id]["current_step"] = "completed"
            # TASKS[task_id]["estimated_remaining"] = 0  # No time remaining
            TASKS[task_id]["result"] = output_chunks

    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time_total
        logging.info(f"[ERROR] Task failed after {total_time:.2f} seconds: {str(e)}")
        TASKS[task_id]["status"] = "failed"  # More consistent status naming
        TASKS[task_id]["error_details"] = str(e)  # Store error details separately
        # TASKS[task_id]["timing"] = {"total_time": round(total_time, 2)}


async def cleanup_tasks():
    # scheduled tasks
    while True:
        now = datetime.now()
        next_midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
        time_to_wait = (next_midnight - now).total_seconds()

        logging.info(
            f"The next cleaning will be performed on {next_midnight}, wait for {time_to_wait} seconds."
        )
        await asyncio.sleep(time_to_wait)
        TASKS.clear()
        logging.info(f"TASKS have been cleared.")
        result_dir = "/app/result"
        for filename in os.listdir(result_dir):
            file_path = os.path.join(result_dir, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        logging.info(f"All files in {result_dir} have been cleared.")


async def start_cleanup():
    asyncio.create_task(cleanup_tasks())


def get_directory_from_file_path(file_path: str) -> str:
    """
    Extract the directory path from a file path.

    Args:
        file_path: Full path to a file
                  (e.g., "/app/result/fb48d287-69c3-48f2-bd8e-c1cc09650b99/fb48d287-69c3-48f2-bd8e-c1cc09650b99.md")

    Returns:
        Directory path (e.g., "/app/result/fb48d287-69c3-48f2-bd8e-c1cc09650b99/")
    """
    directory = os.path.dirname(file_path)

    # Ensure the path ends with a trailing slash
    if not directory.endswith("/"):
        directory += "/"

    return directory


def update_time_estimate(task_id: str, start_time_total: float):
    """Update the estimated remaining time for a task based on progress."""
    if TASKS[task_id]["progress"] > 0:
        elapsed_time = time.time() - start_time_total
        estimated_total = elapsed_time / (TASKS[task_id]["progress"] / 100)
        estimated_remaining = estimated_total - elapsed_time
        TASKS[task_id]["estimated_remaining"] = round(estimated_remaining, 2)
    else:
        TASKS[task_id]["estimated_remaining"] = None
