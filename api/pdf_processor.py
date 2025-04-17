import os
import re
import json
import torch
import httpx
import requests
import base64

from api.config import VL_MODEL_URL, KEY
from magic_pdf.data.data_reader_writer import FileBasedDataWriter
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.utils.office_to_pdf import ConvertToPdfError, convert_file_to_pdf
from pathlib import Path
import tempfile
import shutil


async def download_pdf(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception("PDF retrieval failed")


def extract_pdf(
    task_id: str, pdf_bytes: bytes, start_page: int = 1, end_page: int = None
) -> str:
    name_without_suff = f"/app/result/{task_id}/{task_id}"
    # prepare env
    local_image_dir = f"/app/result/{task_id}/images"
    local_md_dir = f"/app/result/{task_id}"
    image_dir = str(os.path.basename(local_image_dir))
    os.makedirs(local_image_dir, exist_ok=True)

    image_writer = FileBasedDataWriter(local_image_dir)
    md_writer = FileBasedDataWriter(local_md_dir)

    # create Dataset Instance
    ds = PymuDocDataset(pdf_bytes)
    try:
        # inference
        if ds.classify() == SupportedPdfParseMethod.OCR:
            infer_result = ds.apply(
                doc_analyze,
                ocr=True,
                start_page_id=start_page - 1,
                end_page_id=end_page,
            )
            # pipeline
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            infer_result = ds.apply(
                doc_analyze,
                ocr=False,
                start_page_id=start_page - 1,
                end_page_id=end_page,
            )
            # pipeline
            pipe_result = infer_result.pipe_txt_mode(image_writer)
        # dump markdown
        pipe_result.dump_md(md_writer, f"{name_without_suff}.md", image_dir)
        del pipe_result
    finally:
        # release GPU resources
        torch.cuda.empty_cache()
        # waiting for synchronization to ensure release completion
        torch.cuda.synchronize()
    return f"{name_without_suff}.md"


async def check_file_exists(file_path: str) -> bool:
    return os.path.exists(file_path)


async def request_post(url: str, img) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        ret = await client.post(url, files={"file": img})
    if ret.status_code == 200:
        json_file = json.loads(ret.text)
        return json_file["data"]
    else:
        raise Exception("Image URL retrieval failed")


async def process_md(md_path: str, upload_url: str) -> str:
    with open(md_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()
    image_links = re.findall(r"!\[.*?]\((.*?)\)", markdown_text)
    root_image_path = re.search(r"^(.*/)[^/]+$", md_path).group(1)
    if image_links:
        for link in image_links:
            if await check_file_exists(root_image_path + link):
                with open(root_image_path + link, "rb") as img:
                    img_url = await request_post(upload_url, img)
                markdown_text = re.sub(
                    r"!\[.*?]\(" + re.escape(link) + r"\)",
                    f'<img src="{img_url}">',
                    markdown_text,
                )
        with open(md_path, "w", encoding="utf-8") as file:
            file.write(markdown_text)
    return md_path


def read_file(path):
    suffixes = [".ppt", ".pptx", ".doc", ".docx"]
    fns = []
    ret = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for file in files:
                suffix = Path(file).suffix
                if suffix in suffixes:
                    fns.append((os.path.join(root, file)))
    else:
        fns.append(path)
    temp_dir = tempfile.mkdtemp()
    for fn in fns:
        try:
            convert_file_to_pdf(fn, temp_dir)
        except ConvertToPdfError as e:
            raise e
        except FileNotFoundError as e:
            raise e
        except Exception as e:
            raise e
        fn_path = Path(fn)
        pdf_fn = f"{temp_dir}/{fn_path.stem}.pdf"
        with open(pdf_fn, "rb") as f:
            pdf_bytes = f.read()
        ret.append(pdf_bytes)
    shutil.rmtree(temp_dir)
    return ret


def chat_llm_vl(url, param, key):
    headers = {"Authorization": f"Bearer {key}", "content-type": "application/json"}
    ret = requests.post(url, headers=headers, json=param)
    if ret.status_code == 200:
        json_file = json.loads(ret.text)
        res = json_file["choices"][0]["message"]["content"]
        return res
    else:
        raise Exception("Image retrieval failed")


async def gen_img_desc(output_chunks: list):
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(len(output_chunks)):
            chunk_content = output_chunks[i]["content"]
            match_img_urls = re.findall(r'<img\s+src="([^"]+)"', chunk_content)
            if len(match_img_urls) != 0:
                for j in range(len(match_img_urls)):
                    img_url = match_img_urls[j]
                    response = await client.get(img_url)
                    if response.status_code == 200:
                        base64_image = base64.b64encode(response.content).decode(
                            "utf-8"
                        )
                        prompt = [
                            {
                                "type": "text",
                                "text": "请简要描述这张图，**不要超过100字**",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64," + base64_image
                                },
                            },
                        ]
                        messages = [
                            {"role": "user", "content": prompt},
                        ]
                        dic = {
                            "model": "Qwen2.5-VL-72B-Instruct",
                            "messages": messages,
                            "temperature": 0.8,
                            "max_tokens": 4096,
                        }
                        img_desc = chat_llm_vl(VL_MODEL_URL, dic, KEY)
                        pattern = rf'(<img\s+src="{re.escape(img_url)}">)'
                        chunk_content = re.sub(
                            pattern,
                            rf"\1\n上图主要传达的信息是:{img_desc}",
                            chunk_content,
                        )
                    else:
                        raise Exception("Image retrieval failed")
                output_chunks[i]["content"] = chunk_content
            else:
                continue
    return output_chunks
