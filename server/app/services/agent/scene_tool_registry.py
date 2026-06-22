"""
Scene Agent 工具注册 —— 按请求绑定 scene_objects，避免 LangGraph 线程中 ContextVar 丢失。
"""

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from app.services.tools.rag_search import resolve_rag_top_k, search_knowledge_base
from app.services.tools.scene_actions import (
    clear_highlight,
    focus_object,
    highlight_object,
    list_scene_objects,
    move_object,
    rotate_object,
)


def _make_list_objects(objects: list[dict[str, Any]]):
    def scene_list_objects() -> str:
        return list_scene_objects(objects=objects)

    return scene_list_objects


def _make_move(objects: list[dict[str, Any]]):
    def scene_move_object(object_name: str, axis: str, distance: float) -> str:
        try:
            return move_object(object_name, axis, distance, objects=objects)
        except ValueError as exc:
            return str(exc)

    return scene_move_object


def _make_rotate(objects: list[dict[str, Any]]):
    def scene_rotate_object(object_name: str, axis: str, degrees: float) -> str:
        try:
            return rotate_object(object_name, axis, degrees, objects=objects)
        except ValueError as exc:
            return str(exc)

    return scene_rotate_object


def _make_focus(objects: list[dict[str, Any]]):
    def scene_focus_object(object_name: str) -> str:
        try:
            return focus_object(object_name, objects=objects)
        except ValueError as exc:
            return str(exc)

    return scene_focus_object


def _make_highlight(objects: list[dict[str, Any]]):
    def scene_highlight_object(object_name: str) -> str:
        try:
            return highlight_object(object_name, objects=objects)
        except ValueError as exc:
            return str(exc)

    return scene_highlight_object


def create_rag_search_tool(knowledge_base_id: str, top_k: int) -> StructuredTool:
    def _rag_search(query: str) -> str:
        return search_knowledge_base(knowledge_base_id, query, top_k)

    return StructuredTool.from_function(
        func=_rag_search,
        name="rag_search",
        description=(
            "在当前知识库中检索与问题相关的文档片段。"
            "输入应为简洁的检索关键词或问句；返回检索到的资料摘要。"
        ),
    )


def get_scene_agent_tools(
    scene_objects: list[dict[str, Any]],
    knowledge_base_id: str | None = None,
    top_k: int | None = None,
) -> list[BaseTool]:
    """Scene Agent 工具：场景控制（绑定 objects 快照）+ 可选 rag_search。"""
    objects_snapshot = [dict(item) for item in scene_objects]

    tools: list[BaseTool] = [
        StructuredTool.from_function(
            func=_make_list_objects(objects_snapshot),
            name="scene_list_objects",
            description="列出当前 3D 场景中所有已加载对象及其位置、旋转信息。",
        ),
        StructuredTool.from_function(
            func=_make_move(objects_snapshot),
            name="scene_move_object",
            description="平移场景对象。object_name 为对象名称、id 或「第一个」；axis 为 x/y/z；distance 为米。",
        ),
        StructuredTool.from_function(
            func=_make_rotate(objects_snapshot),
            name="scene_rotate_object",
            description="旋转场景对象。object_name 为对象名称、id 或「第一个」；axis 为 x/y/z；degrees 为角度。",
        ),
        StructuredTool.from_function(
            func=_make_focus(objects_snapshot),
            name="scene_focus_object",
            description="将相机聚焦到指定对象。object_name 为对象名称、id 或「第一个」。",
        ),
        StructuredTool.from_function(
            func=_make_highlight(objects_snapshot),
            name="scene_highlight_object",
            description="高亮指定对象。object_name 为对象名称、id 或「第一个」。",
        ),
        StructuredTool.from_function(
            func=lambda: clear_highlight(),
            name="scene_clear_highlight",
            description="清除场景中所有高亮。",
        ),
    ]

    if knowledge_base_id:
        effective_top_k = resolve_rag_top_k(top_k)
        tools.append(create_rag_search_tool(knowledge_base_id, effective_top_k))
    return tools
