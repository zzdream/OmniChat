"""解析器公共工具。"""

from app.services.rag.errors import IngestError


def require_non_empty(text: str, *, empty_message: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise IngestError(empty_message)
    return cleaned
