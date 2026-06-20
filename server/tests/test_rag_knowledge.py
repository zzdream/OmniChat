"""RAG 知识库与流式接口测试 —— mock Embedding / LLM，不依赖 BGE 模型。"""

from unittest.mock import patch

from app.services.rag.knowledge_service import run_document_indexing
from app.services.rag.retrieve import RetrievedChunk


def test_create_and_list_knowledge_base(client) -> None:
    response = client.post("/knowledge/bases", json={"name": "测试库", "description": "demo"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "测试库"
    assert body["document_count"] == 0

    listed = client.get("/knowledge/bases")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_upload_document_mocked(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "文档库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=2,
    ):
        response = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={"file": ("note.md", b"# hello\n\nRAG test content here.", "text/markdown")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"

    run_document_indexing(body["id"])

    listed = client.get(f"/knowledge/bases/{kb_id}/documents")
    assert listed.json()[0]["status"] == "indexed"
    assert listed.json()[0]["chunk_count"] == 2


def test_rag_stream_returns_sources(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "问答库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=1,
    ):
        upload = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={"file": ("faq.md", "RAG 是检索增强生成".encode(), "text/markdown")},
        )
        run_document_indexing(upload.json()["id"])

    chunks = [
        RetrievedChunk(
            document_id="doc-1",
            filename="faq.md",
            chunk_index=0,
            content="RAG 是检索增强生成",
            score=0.91,
        )
    ]

    def fake_stream(*args, **kwargs):
        yield "你好"

    with patch("app.api.routes.chat_rag.retrieve", return_value=chunks):
        with patch("app.api.routes.chat_rag.chat_completion_stream", side_effect=fake_stream):
            response = client.post(
                "/chat/rag/stream",
                json={
                    "message": "什么是 RAG？",
                    "knowledge_base_id": kb_id,
                },
            )

    assert response.status_code == 200
    assert "sources" in response.text
    assert "检索增强生成" in response.text
    assert "done" in response.text


def test_upload_pdf_extension_allowed(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "PDF库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=3,
    ):
        response = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()["filename"] == "report.pdf"


def test_upload_docx_extension_allowed(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "Word库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=2,
    ):
        response = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={
                "file": (
                    "notes.docx",
                    b"PK\x03\x04",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["filename"] == "notes.docx"


def test_upload_doc_extension_allowed(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "旧Word库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=2,
    ):
        response = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={"file": ("legacy.doc", b"\xd0\xcf\x11\xe0", "application/msword")},
        )

    assert response.status_code == 200
    assert response.json()["filename"] == "legacy.doc"


def test_upload_xlsx_extension_allowed(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "Excel库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=2,
    ):
        response = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={
                "file": (
                    "data.xlsx",
                    b"PK\x03\x04",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["filename"] == "data.xlsx"


def test_upload_pptx_extension_allowed(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "PPT库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=2,
    ):
        response = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={
                "file": (
                    "slides.pptx",
                    b"PK\x03\x04",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["filename"] == "slides.pptx"


def test_upload_png_extension_allowed(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "图片库"})
    kb_id = create.json()["id"]

    with patch(
        "app.services.rag.knowledge_service.index_document",
        return_value=1,
    ):
        response = client.post(
            f"/knowledge/bases/{kb_id}/documents",
            files={"file": ("scan.png", b"\x89PNG\r\n", "image/png")},
        )

    assert response.status_code == 200
    assert response.json()["filename"] == "scan.png"


def test_upload_unsupported_extension_rejected(client) -> None:
    create = client.post("/knowledge/bases", json={"name": "校验库"})
    kb_id = create.json()["id"]

    response = client.post(
        f"/knowledge/bases/{kb_id}/documents",
        files={"file": ("clip.gif", b"fake", "image/gif")},
    )

    assert response.status_code == 400
    assert ".png" in response.json()["detail"]
