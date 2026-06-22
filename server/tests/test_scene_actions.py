"""Scene 工具单元测试"""

import json

import pytest

from app.services.tools.scene_actions import (
    clear_highlight,
    focus_object,
    move_object,
    rotate_object,
)
from app.services.tools.scene_context import set_scene_objects_buffer


@pytest.fixture
def scene_objects():
    return set_scene_objects_buffer(
        [
            {
                "id": "obj-1",
                "name": "红色立方体",
                "fileName": "bus.glb",
                "position": {"x": 1, "y": 0, "z": 2},
                "rotation": {"x": 0, "y": 0, "z": 0},
                "scale": {"x": 1, "y": 1, "z": 1},
            }
        ]
    )


def test_move_object_returns_action_json(scene_objects) -> None:
    result = move_object("红色立方体", "x", 2, objects=scene_objects)
    payload = json.loads(result)
    assert payload["action"] == "move"
    assert payload["object_id"] == "obj-1"
    assert payload["axis"] == "x"
    assert payload["distance"] == 2


def test_rotate_object_by_ordinal(scene_objects) -> None:
    result = rotate_object("第一个", "y", 45, objects=scene_objects)
    payload = json.loads(result)
    assert payload["action"] == "rotate"
    assert payload["degrees"] == 45


def test_find_by_filename_without_extension(scene_objects) -> None:
    result = rotate_object("bus.glb", "y", 10, objects=scene_objects)
    payload = json.loads(result)
    assert payload["action"] == "rotate"


def test_focus_object_not_found() -> None:
    set_scene_objects_buffer([])
    with pytest.raises(ValueError, match="未找到对象"):
        focus_object("missing")


def test_clear_highlight(scene_objects) -> None:
    result = clear_highlight()
    assert json.loads(result)["action"] == "clear_highlight"
