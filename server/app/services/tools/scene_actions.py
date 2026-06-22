"""
3D 场景动作 —— 校验参数并返回供前端执行的 JSON 指令。
"""

import json
from typing import Any

from app.services.tools.scene_context import SceneObjectRecord, find_scene_object, resolve_scene_objects

VALID_AXES = frozenset({"x", "y", "z"})
SCENE_TOOL_NAMES = frozenset(
    {
        "scene_list_objects",
        "scene_move_object",
        "scene_rotate_object",
        "scene_focus_object",
        "scene_highlight_object",
        "scene_clear_highlight",
    }
)


def _action_payload(action: str, **kwargs: Any) -> str:
    return json.dumps({"action": action, **kwargs}, ensure_ascii=False)


def list_scene_objects(objects: list[SceneObjectRecord] | None = None) -> str:
    """列出当前场景中的所有对象及其变换信息。"""
    buffer = resolve_scene_objects(objects)
    if not buffer:
        return "当前场景中没有已加载的 3D 对象。请提示用户上传 GLB 模型。"

    lines: list[str] = []
    for index, item in enumerate(buffer, start=1):
        pos = item.get("position", {})
        rot = item.get("rotation", {})
        lines.append(
            f"{index}. {item.get('name')} (id={item.get('id')}): "
            f"位置({pos.get('x', 0)}, {pos.get('y', 0)}, {pos.get('z', 0)}), "
            f"旋转({rot.get('x', 0)}, {rot.get('y', 0)}, {rot.get('z', 0)})"
        )
    return "\n".join(lines)


def move_object(
    object_name: str,
    axis: str,
    distance: float,
    *,
    objects: list[SceneObjectRecord] | None = None,
) -> str:
    """沿指定轴平移场景对象（单位：米）。axis 可选 x、y、z。"""
    obj = find_scene_object(object_name, objects)
    if obj is None:
        raise ValueError(f"未找到对象: {object_name}")

    axis_key = axis.strip().lower()
    if axis_key not in VALID_AXES:
        raise ValueError(f"axis 必须是 x、y、z 之一，收到: {axis}")

    return _action_payload(
        "move",
        object_id=obj["id"],
        object_name=obj.get("name", object_name),
        axis=axis_key,
        distance=float(distance),
    )


def rotate_object(
    object_name: str,
    axis: str,
    degrees: float,
    *,
    objects: list[SceneObjectRecord] | None = None,
) -> str:
    """绕指定轴旋转场景对象（单位：度）。axis 可选 x、y、z。"""
    obj = find_scene_object(object_name, objects)
    if obj is None:
        raise ValueError(f"未找到对象: {object_name}")

    axis_key = axis.strip().lower()
    if axis_key not in VALID_AXES:
        raise ValueError(f"axis 必须是 x、y、z 之一，收到: {axis}")

    return _action_payload(
        "rotate",
        object_id=obj["id"],
        object_name=obj.get("name", object_name),
        axis=axis_key,
        degrees=float(degrees),
    )


def focus_object(object_name: str, *, objects: list[SceneObjectRecord] | None = None) -> str:
    """将相机聚焦到指定对象。"""
    obj = find_scene_object(object_name, objects)
    if obj is None:
        raise ValueError(f"未找到对象: {object_name}")

    return _action_payload(
        "focus",
        object_id=obj["id"],
        object_name=obj.get("name", object_name),
    )


def highlight_object(object_name: str, *, objects: list[SceneObjectRecord] | None = None) -> str:
    """高亮指定对象。"""
    obj = find_scene_object(object_name, objects)
    if obj is None:
        raise ValueError(f"未找到对象: {object_name}")

    return _action_payload(
        "highlight",
        object_id=obj["id"],
        object_name=obj.get("name", object_name),
    )


def clear_highlight() -> str:
    """清除所有对象高亮。"""
    return _action_payload("clear_highlight")
