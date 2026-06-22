"""
Phase 4 Scene Agent 配置 —— 独立于 Phase 1–3。
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class SceneSettings:
    """3D Scene Agent 相关环境变量"""

    rate_limit_scene: str = os.getenv("RATE_LIMIT_SCENE", "10/minute")
    scene_default_system: str = os.getenv(
        "SCENE_DEFAULT_SYSTEM",
        "你是 3D 场景智能助手，可以查看和控制用户上传的 GLB 模型。"
        "使用 scene_list_objects 了解场景中有哪些对象。"
        "用户要求移动、旋转、聚焦或高亮对象时，调用对应的 scene_* 工具。"
        "工具返回的 JSON 指令会由前端在浏览器中执行。"
        "若绑定了知识库，可使用 rag_search 检索场景相关文档后再回答。"
        "回答时用自然语言说明已完成的操作或检索结果。",
    )
    scene_rag_system_suffix: str = os.getenv(
        "SCENE_RAG_SYSTEM_SUFFIX",
        "当前已绑定知识库「{kb_name}」。"
        "遇到需要依据资料回答的问题，请先调用 rag_search 检索，"
        "必要时再结合 scene_* 工具操作场景。",
    )


@lru_cache
def get_scene_settings() -> SceneSettings:
    return SceneSettings()
