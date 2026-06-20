"""借助系统工具解析旧版 Office（.ppt 等）。"""

import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.services.rag.errors import IngestError


def extract_text_with_system_converter(file_path: Path) -> str:
    if shutil.which("textutil") and platform.system() == "Darwin":
        result = subprocess.run(
            ["textutil", "-stdout", "-convert", "txt", str(file_path)],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            text = result.stdout.decode("utf-8", errors="replace").strip()
            if text:
                return text

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "txt",
                    "--outdir",
                    str(out_dir),
                    str(file_path),
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                txt_files = list(out_dir.glob("*.txt"))
                if txt_files:
                    text = txt_files[0].read_text(encoding="utf-8", errors="replace").strip()
                    if text:
                        return text

    raise IngestError(
        "无法解析旧版 .ppt 文件，请另存为 .pptx，或在服务器安装 LibreOffice"
    )
