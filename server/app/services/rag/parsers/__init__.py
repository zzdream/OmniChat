"""按扩展名分发文档解析，便于后续扩展 Word / Excel / PPT / 图片等格式。"""

from pathlib import Path

from app.config_rag import get_rag_settings
from app.services.rag.errors import IngestError
from app.services.rag.parsers.excel import parse_xls_file, parse_xlsx_file
from app.services.rag.parsers.image import parse_image_file
from app.services.rag.parsers.pdf import parse_pdf_file
from app.services.rag.parsers.ppt import parse_ppt_file, parse_pptx_file
from app.services.rag.parsers.text import parse_text_file
from app.services.rag.parsers.word import parse_doc_file, parse_docx_file

_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".markdown"})
_PDF_EXTENSIONS = frozenset({".pdf"})
_DOCX_EXTENSIONS = frozenset({".docx"})
_DOC_EXTENSIONS = frozenset({".doc"})
_XLSX_EXTENSIONS = frozenset({".xlsx"})
_XLS_EXTENSIONS = frozenset({".xls"})
_PPTX_EXTENSIONS = frozenset({".pptx"})
_PPT_EXTENSIONS = frozenset({".ppt"})
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def parse_document(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    settings = get_rag_settings()

    if suffix not in settings.allowed_extensions:
        allowed = "、".join(sorted(settings.allowed_extensions))
        raise IngestError(f"不支持的文件类型: {suffix}，仅支持: {allowed}")

    if suffix in _TEXT_EXTENSIONS:
        return parse_text_file(file_path)
    if suffix in _PDF_EXTENSIONS:
        return parse_pdf_file(file_path)
    if suffix in _DOCX_EXTENSIONS:
        return parse_docx_file(file_path)
    if suffix in _DOC_EXTENSIONS:
        return parse_doc_file(file_path)
    if suffix in _XLSX_EXTENSIONS:
        return parse_xlsx_file(file_path)
    if suffix in _XLS_EXTENSIONS:
        return parse_xls_file(file_path)
    if suffix in _PPTX_EXTENSIONS:
        return parse_pptx_file(file_path)
    if suffix in _PPT_EXTENSIONS:
        return parse_ppt_file(file_path)
    if suffix in _IMAGE_EXTENSIONS:
        return parse_image_file(file_path)

    raise IngestError(f"尚未实现该格式的解析: {suffix}")
