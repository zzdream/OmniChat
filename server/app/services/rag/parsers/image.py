"""图片 OCR 解析。"""

from pathlib import Path

from app.services.rag.errors import IngestError
from app.services.rag.ocr import ocr_image_path
from app.services.rag.parsers._utils import require_non_empty


def parse_image_file(file_path: Path) -> str:
    try:
        text = ocr_image_path(file_path)
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError(f"无法读取图片: {exc}") from exc

    return require_non_empty(text, empty_message="图片 OCR 未识别到文字")
