import asyncio
import logging
import os

# logging setting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

UPLOAD_URL = "https://km-search-api.tao.inventec.net/upload"

TASKS = {}

# control the concurrent quantity for PDF processing
SEMAPHORE_LIMIT = int(os.getenv("PDF_PROCESSOR_SEMAPHORE", "4"))
SEMAPHORE = asyncio.Semaphore(SEMAPHORE_LIMIT)

# control the concurrent quantity for image description generation
IMG_DESC_SEMAPHORE_LIMIT = int(os.getenv("IMG_DESC_SEMAPHORE", "8"))

# Log the semaphore values
logging.info(f"PDF_PROCESSOR_SEMAPHORE set to {SEMAPHORE_LIMIT}")
logging.info(f"IMG_DESC_SEMAPHORE set to {IMG_DESC_SEMAPHORE_LIMIT}")

# Qwen2.5-72B-VL
VL_MODEL_URL = "http://172.123.100.103:4000/v1/chat/completions"
KEY = "sk-E3bVLke1aSFGgSpMC38aCe8e5c5746F99736Ae22A2856543"
