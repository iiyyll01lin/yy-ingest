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

# Qwen2.5-72B-VL
VL_MODEL_URL = "http://10.3.30.13:4000/v1/chat/completions"
KEY = "sk-E3bVLke1aSFGgSpMC38aCe8e5c5746F99736Ae22A2856543"
