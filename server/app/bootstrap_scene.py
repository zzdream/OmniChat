"""
Phase 4 Scene Agent 引导 —— 注册路由，不修改 Phase 1–3 业务模块。
"""

from fastapi import FastAPI

from app.api.routes import chat_scene


def setup_scene(app: FastAPI) -> None:
    """挂载 3D Scene Agent 路由。"""
    app.include_router(chat_scene.router)
