"""
3D 场景上下文 —— 请求级 scene_objects，供 Scene Agent 工具读取。
"""

from contextvars import ContextVar
from typing import Any

SceneObjectRecord = dict[str, Any]

_scene_objects_buffer: ContextVar[list[SceneObjectRecord] | None] = ContextVar(
    "_scene_objects_buffer",
    default=None,
)

_ORDINAL_ALIASES: dict[str, int] = {
    "第一个": 0,
    "第一个模型": 0,
    "首个": 0,
    "首个模型": 0,
    "first": 0,
    "1": 0,
}


def set_scene_objects_buffer(objects: list[SceneObjectRecord]) -> list[SceneObjectRecord]:
    """为当前请求设置场景对象列表，返回同一列表供写入。"""
    _scene_objects_buffer.set(objects)
    return objects


def get_scene_objects_buffer() -> list[SceneObjectRecord] | None:
    return _scene_objects_buffer.get()


def resolve_scene_objects(objects: list[SceneObjectRecord] | None = None) -> list[SceneObjectRecord]:
    if objects is not None:
        return objects
    return get_scene_objects_buffer() or []


def _normalize_key(value: str) -> str:
    text = value.strip().lower()
    for suffix in (".glb", ".gltf"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def find_scene_object(
    name: str,
    objects: list[SceneObjectRecord] | None = None,
) -> SceneObjectRecord | None:
    buffer = resolve_scene_objects(objects)
    if not buffer:
        return None

    raw = name.strip()
    key = _normalize_key(raw)

    if key in _ORDINAL_ALIASES:
        index = _ORDINAL_ALIASES[key]
        if index < len(buffer):
            return buffer[index]

    for item in buffer:
        obj_id = _normalize_key(str(item.get("id", "")))
        obj_name = _normalize_key(str(item.get("name", "")))
        file_name = _normalize_key(str(item.get("fileName", "")))
        if key in {obj_id, obj_name, file_name}:
            return item
    return None
