"""OCR 文字识别 —— RapidOCR（ONNX），输出纯文本供 BGE-M3 向量化。"""

from pathlib import Path
from typing import Any

from app.config_rag import get_rag_settings
from app.services.rag.errors import IngestError

_engine: Any | None = None


def _ensure_ocr_enabled() -> None:
    if not get_rag_settings().ocr_enabled:
        raise IngestError("OCR 未启用，请在环境变量中设置 RAG_OCR_ENABLED=true")


def _load_engine() -> Any:
    global _engine
    if _engine is not None:
        return _engine

    _ensure_ocr_enabled()
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise IngestError(
            "未安装 OCR 依赖，请执行: pip install rapidocr-onnxruntime opencv-python-headless"
        ) from exc

    _engine = RapidOCR()
    return _engine


def _format_ocr_result(result: list | None) -> str:
    if not result:
        return ""

    lines: list[str] = []
    for item in result:
        if len(item) < 2:
            continue
        text = str(item[1]).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def ocr_image_path(file_path: Path) -> str:
    engine = _load_engine()
    try:
        result, _ = engine(str(file_path))
    except Exception as exc:
        raise IngestError(f"图片 OCR 失败: {exc}") from exc
    return _format_ocr_result(result)


def ocr_image_bytes(image_bytes: bytes) -> str:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise IngestError(
            "未安装 opencv-python-headless，请执行: pip install opencv-python-headless"
        ) from exc

    engine = _load_engine()
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise IngestError("无法解码图片数据")

    try:
        result, _ = engine(image)
    except Exception as exc:
        raise IngestError(f"OCR 识别失败: {exc}") from exc
    return _format_ocr_result(result)


def ocr_pdf_pages(file_path: Path, page_indices: list[int]) -> dict[int, str]:
    """对 PDF 指定页（0-based）渲染为图后 OCR，返回 {页码(1-based): 文本}。"""
    if not page_indices:
        return {}

    try:
        import fitz
    except ImportError as exc:
        raise IngestError("未安装 pymupdf，请执行: pip install pymupdf") from exc

    settings = get_rag_settings()
    if len(page_indices) > settings.ocr_max_pdf_pages:
        raise IngestError(
            f"需 OCR 的 PDF 页数超过上限（{settings.ocr_max_pdf_pages} 页），"
            "请拆分文件或调大 RAG_OCR_MAX_PDF_PAGES"
        )

    matrix = fitz.Matrix(settings.ocr_pdf_zoom, settings.ocr_pdf_zoom)
    results: dict[int, str] = {}

    try:
        document = fitz.open(str(file_path))
    except Exception as exc:
        raise IngestError(f"无法打开 PDF 进行 OCR: {exc}") from exc

    try:
        for page_index in page_indices:
            if page_index < 0 or page_index >= document.page_count:
                continue
            page = document[page_index]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            text = ocr_image_bytes(pixmap.tobytes("png"))
            if text.strip():
                results[page_index + 1] = text.strip()
    finally:
        document.close()

    return results
