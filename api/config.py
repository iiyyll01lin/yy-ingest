import asyncio
import logging

# logging setting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

UPLOAD_URL = "https://km-search-api.tao.inventec.net/upload"

TASKS = {}

# control the concurrent quantity
SEMAPHORE = asyncio.Semaphore(4)
