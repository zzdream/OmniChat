"""纯文本 / Markdown 解析。"""

from pathlib import Path

from app.services.rag.errors import IngestError


def parse_text_file(file_path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise IngestError("无法识别文件编码，请使用 UTF-8 文本")
