import os
import re
import json
import torch
import httpx

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


def extract_pdf(task_id: str, pdf_bytes: bytes, start_page: int = 1, end_page: int = None) -> str:
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
            infer_result = ds.apply(doc_analyze, ocr=True, start_page_id=start_page - 1, end_page_id=end_page)
            # pipeline
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            infer_result = ds.apply(doc_analyze, ocr=False, start_page_id=start_page - 1, end_page_id=end_page)
            # pipeline
            pipe_result = infer_result.pipe_txt_mode(image_writer)
        # dump markdown
        pipe_result.dump_md(md_writer, f"{name_without_suff}.md", image_dir)
    finally:
        # release GPU resources
        del pipe_result
        torch.cuda.empty_cache()
        # waiting for synchronization to ensure release completion
        torch.cuda.synchronize()
    return f"{name_without_suff}.md"


async def check_file_exists(file_path: str) -> bool:
    return os.path.exists(file_path)


async def request_post(url: str, img) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        ret = await client.post(url, files={'file': img})
    if ret.status_code == 200:
        json_file = json.loads(ret.text)
        return json_file['data']
    else:
        raise Exception("Image URL retrieval failed")


async def process_md(md_path: str, upload_url: str) -> str:
    with open(md_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()
    image_links = re.findall(r'!\[.*?]\((.*?)\)', markdown_text)
    root_image_path = re.search(r'^(.*/)[^/]+$', md_path).group(1)
    if image_links:
        for link in image_links:
            if await check_file_exists(root_image_path + link):
                with open(root_image_path + link, 'rb') as img:
                    img_url = await request_post(upload_url, img)
                markdown_text = re.sub(r'!\[.*?]\(' + re.escape(link) + r'\)', f'<img src="{img_url}">', markdown_text)
        with open(md_path, 'w', encoding='utf-8') as file:
            file.write(markdown_text)
    return md_path
    

def read_file(path):
    suffixes = ['.ppt', '.pptx', '.doc', '.docx']
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
        with open(pdf_fn, 'rb') as f:
            pdf_bytes = f.read()
        ret.append(pdf_bytes)
    shutil.rmtree(temp_dir)
    return ret
