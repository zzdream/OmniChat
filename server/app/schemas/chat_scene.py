"""
POST /chat/scene/stream 的请求体 —— Phase 4 Scene Agent。
"""

from pydantic import BaseModel, Field

from app.schemas.chat_agent import AgentChatRequest


class SceneObjectSnapshot(BaseModel):
    """前端上报的场景对象快照。"""

    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    fileName: str | None = Field(default=None, max_length=256)
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    rotation: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    scale: dict[str, float] = Field(default_factory=lambda: {"x": 1, "y": 1, "z": 1})


class SceneChatRequest(AgentChatRequest):
    """Scene Agent 请求 —— 在 Agent 基础上附加场景对象与选中对象。"""

    scene_objects: list[SceneObjectSnapshot] = Field(
        default_factory=list,
        description="当前场景中已加载对象的快照列表",
    )
    selected_object_id: str | None = Field(
        default=None,
        description="用户当前选中的对象 id",
    )
