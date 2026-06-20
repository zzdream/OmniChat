"""PDF 文本提取：优先抽取可选中文本，扫描页回退 OCR。"""

from pathlib import Path

from pypdf import PdfReader

from app.config_rag import get_rag_settings
from app.services.rag.errors import IngestError
from app.services.rag.ocr import ocr_pdf_pages
from app.services.rag.parsers._utils import require_non_empty


def _extract_pdf_text_pages(file_path: Path) -> tuple[list[tuple[int, str]], list[int]]:
    try:
        reader = PdfReader(str(file_path))
    except Exception as exc:
        raise IngestError(f"无法读取 PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise IngestError("PDF 已加密，无法提取文本") from exc

    text_pages: list[tuple[int, str]] = []
    ocr_page_indices: list[int] = []

    for index, page in enumerate(reader.pages):
        page_number = index + 1
        try:
            page_text = (page.extract_text() or "").strip()
        except Exception as exc:
            raise IngestError(f"PDF 第 {page_number} 页解析失败: {exc}") from exc

        if page_text:
            text_pages.append((page_number, page_text))
        else:
            ocr_page_indices.append(index)

    return text_pages, ocr_page_indices


def parse_pdf_file(file_path: Path) -> str:
    text_pages, ocr_page_indices = _extract_pdf_text_pages(file_path)
    settings = get_rag_settings()

    if ocr_page_indices:
        if not settings.ocr_enabled:
            if text_pages:
                combined = "\n\n".join(text for _, text in text_pages).strip()
                return require_non_empty(
                    combined,
                    empty_message="PDF 含扫描页且 OCR 未启用，请设置 RAG_OCR_ENABLED=true",
                )
            raise IngestError(
                "PDF 未提取到文本，可能是扫描件；请设置 RAG_OCR_ENABLED=true 以启用 OCR"
            )

        ocr_pages = ocr_pdf_pages(file_path, ocr_page_indices)
        for page_number in sorted(ocr_pages):
            text_pages.append((page_number, ocr_pages[page_number]))

    text_pages.sort(key=lambda item: item[0])
    combined = "\n\n".join(text for _, text in text_pages).strip()
    return require_non_empty(
        combined,
        empty_message="PDF 未提取到文本，可能是空白文件或 OCR 未识别到内容",
    )
