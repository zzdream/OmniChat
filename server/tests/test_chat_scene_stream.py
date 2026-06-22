"""Scene Agent 接口测试"""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient


def parse_sse_events(text: str) -> list[dict]:
    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@patch("app.api.routes.chat_scene.iter_scene_agent_events")
def test_scene_stream_sse(mock_iter, client: TestClient) -> None:
    mock_iter.return_value = iter(
        [
            {
                "tool_call": {
                    "id": "c1",
                    "name": "scene_move_object",
                    "arguments": '{"object_name":"cube","axis":"x","distance":2}',
                }
            },
            {
                "tool_result": {
                    "id": "c1",
                    "name": "scene_move_object",
                    "result": '{"action":"move","object_id":"obj-1","axis":"x","distance":2}',
                }
            },
            {
                "scene_action": {
                    "action": "move",
                    "object_id": "obj-1",
                    "axis": "x",
                    "distance": 2,
                }
            },
            {"content": "已将对象向右移动 2 米"},
            {"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
        ]
    )

    response = client.post(
        "/chat/scene/stream",
        json={
            "message": "把立方体向右移 2 米",
            "scene_objects": [
                {
                    "id": "obj-1",
                    "name": "cube",
                    "position": {"x": 0, "y": 0, "z": 0},
                    "rotation": {"x": 0, "y": 0, "z": 0},
                    "scale": {"x": 1, "y": 1, "z": 1},
                }
            ],
        },
    )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    assert events[0]["tool_call"]["name"] == "scene_move_object"
    assert events[2]["scene_action"]["action"] == "move"
    assert events[-1] == {"done": True}
