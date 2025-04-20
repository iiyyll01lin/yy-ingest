import asyncio
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.models import RequestData, ResponseData
from api.tasks import task_runner, start_cleanup
from api.config import TASKS
from contextlib import asynccontextmanager
import logging

# logging setting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


@asynccontextmanager
async def startup_event(app: FastAPI):
    await start_cleanup()
    yield


app = FastAPI(lifespan=startup_event)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=getattr(exc, "status_code", 500),
        content={"state": False, "msg": str(exc), "data": None},
    )


@app.post("/transform")
async def transform(request_data: RequestData):
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "pending", "result": None}
    asyncio.create_task(
        task_runner(
            task_id=task_id,
            url=request_data.url,
            start_page=request_data.start_page,
            end_page=request_data.end_page,
            chunk_method=request_data.chunk_method,
            chunk_max_size=request_data.chunk_max_size,
            chunk_size=request_data.chunk_size,
            chunk_overlap=request_data.chunk_overlap,
            avg_chunk_size=request_data.avg_chunk_size,
            encoding_name=request_data.encoding_name,
            # LANGCHAIN_MARKDOWN
            headers_to_split_on=request_data.headers_to_split_on,
            return_each_line=request_data.return_each_line,
            strip_headers=request_data.strip_headers,
        )
    )
    return ResponseData(data=task_id)
    # return ResponseData(data=task_id, duration="started")


@app.get("/status/{task_id}")
async def check_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return ResponseData(state=False, msg="Task not found", data=None)

    # When task is still processing
    if task["status"] in [
        "pending",
        "extracting",
        "chunking",
        "generate image description",
    ]:

        response_data = None
        # Return progress information without the full result
        # response_data = {
        #     "progress": task.get("progress", 0),  # Add progress tracking
        #     "current_step": task.get("current_step", ""),  # Add step tracking
        #     "timing": task.get("timing", {})  # Include timing if available
        # }
        return ResponseData(
            # state=True,
            msg=task["status"],
            data=response_data,
            # duration=task.get("timing")
        )

    # When task completed successfully
    elif task["status"] == "success":
        return ResponseData(
            # state=True,
            msg=task["status"],
            data=task["result"],
            # duration=task["timing"]
        )

    # When task failed
    else:
        error_details = task.get("error_details", task["status"])
        return ResponseData(
            state=False,
            msg=error_details,
            # data={"error": error_details},
            # duration=task.get("timing")
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8753)
