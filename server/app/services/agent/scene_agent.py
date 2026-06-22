"""
Scene Agent 编排 —— LangChain Agent + 3D 场景工具，独立于 Phase 3 langchain_agent。
"""

import json
from collections.abc import Iterator
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError

from app.config import Settings, get_settings
from app.config_agent import get_agent_settings
from app.config_retry import get_retry_settings
from app.config_scene import SceneSettings, get_scene_settings
from app.services.agent.langchain_agent import (
    AgentRunError,
    _accumulate_usage,
    _content_to_str,
    build_langchain_messages,
)
from app.services.agent.scene_tool_registry import get_scene_agent_tools
from app.services.llm import LLMConfigError
from app.services.llm_retry import get_chat_openai_max_retries, is_retryable_api_error
from app.services.tools.rag_search import get_rag_sources_buffer, set_rag_sources_buffer
from app.services.tools.scene_actions import SCENE_TOOL_NAMES
from app.services.tools.scene_context import set_scene_objects_buffer


def _resolve_scene_system_prompt(
    system_prompt: str | None,
    scene_config: SceneSettings,
    *,
    knowledge_base_name: str | None = None,
) -> str:
    base = system_prompt or scene_config.scene_default_system
    if knowledge_base_name:
        suffix = scene_config.scene_rag_system_suffix.format(kb_name=knowledge_base_name)
        return f"{base}\n{suffix}"
    return base


def _inject_scene_context(
    user_message: str,
    scene_objects: list[dict[str, Any]],
    selected_object_id: str | None,
) -> str:
    if not scene_objects and not selected_object_id:
        return user_message

    lines = ["【当前 3D 场景上下文】"]
    if scene_objects:
        lines.append(f"已加载 {len(scene_objects)} 个对象：")
        for item in scene_objects:
            marker = " ← 用户当前选中" if item.get("id") == selected_object_id else ""
            pos = item.get("position", {})
            lines.append(
                f"  - {item.get('name')} (id={item.get('id')}) "
                f"位置({pos.get('x', 0):.2f}, {pos.get('y', 0):.2f}, {pos.get('z', 0):.2f})"
                f"{marker}"
            )
    elif selected_object_id:
        lines.append(f"用户选中对象 id: {selected_object_id}")

    lines.append("")
    lines.append(f"【用户问题】\n{user_message}")
    return "\n".join(lines)


def create_scene_agent(
    *,
    system_prompt: str,
    model: str | None = None,
    temperature: float | None = None,
    settings: Settings | None = None,
    knowledge_base_id: str | None = None,
    top_k: int | None = None,
    scene_objects: list[dict[str, Any]] | None = None,
):
    config = settings or get_settings()
    if not config.deepseek_api_key:
        raise LLMConfigError("DEEPSEEK_API_KEY 未配置，请在 .env 中设置")

    llm = ChatOpenAI(
        model=model or config.deepseek_model,
        api_key=config.deepseek_api_key,
        base_url=config.deepseek_base_url,
        temperature=(
            temperature if temperature is not None else config.chat_default_temperature
        ),
        max_retries=get_chat_openai_max_retries(get_retry_settings()),
    )
    tools = get_scene_agent_tools(scene_objects or [], knowledge_base_id, top_k)
    return create_agent(llm, tools, system_prompt=system_prompt)


def _maybe_parse_scene_action(tool_name: str, result: str) -> dict[str, Any] | None:
    if tool_name not in SCENE_TOOL_NAMES:
        return None
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and payload.get("action"):
        return payload
    return None


def iter_scene_agent_events(
    user_message: str,
    system_prompt: str | None = None,
    history: list[dict[str, str]] | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    settings: Settings | None = None,
    scene_settings: SceneSettings | None = None,
    knowledge_base_id: str | None = None,
    top_k: int | None = None,
    knowledge_base_name: str | None = None,
    scene_objects: list[dict[str, Any]] | None = None,
    selected_object_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    """
    运行 Scene Agent 并产出 SSE 事件。

    在 tool_result 之外，对 scene_* 工具额外产出 scene_action 事件供前端执行。
    """
    config = settings or get_settings()
    scene_config = scene_settings or get_scene_settings()
    agent_config = get_agent_settings()
    system = _resolve_scene_system_prompt(
        system_prompt,
        scene_config,
        knowledge_base_name=knowledge_base_name,
    )

    objects_payload = [dict(item) for item in (scene_objects or [])]
    set_scene_objects_buffer(objects_payload)
    set_rag_sources_buffer()
    emitted_source_count = 0

    enriched_message = _inject_scene_context(user_message, objects_payload, selected_object_id)

    try:
        agent = create_scene_agent(
            system_prompt=system,
            model=model,
            temperature=temperature,
            settings=config,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            scene_objects=objects_payload,
        )
    except LLMConfigError:
        raise

    messages = build_langchain_messages(enriched_message, history, settings=config)
    run_config = {"recursion_limit": agent_config.agent_max_iterations}
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    final_content: str | None = None
    retry_settings = get_retry_settings()
    max_attempts = (
        retry_settings.llm_retry_max_attempts if retry_settings.llm_retry_enabled else 1
    )

    try:
        for run_attempt in range(1, max_attempts + 1):
            emitted_any = False
            try:
                for chunk in agent.stream(
                    {"messages": messages},
                    config=run_config,
                    stream_mode="updates",
                ):
                    emitted_any = True
                    for _node, update in chunk.items():
                        for message in update.get("messages", []):
                            if isinstance(message, AIMessage):
                                _accumulate_usage(message, usage_totals)

                                if message.tool_calls:
                                    for tool_call in message.tool_calls:
                                        yield {
                                            "tool_call": {
                                                "id": tool_call["id"],
                                                "name": tool_call["name"],
                                                "arguments": json.dumps(
                                                    tool_call["args"],
                                                    ensure_ascii=False,
                                                ),
                                            }
                                        }
                                    continue

                                content = _content_to_str(message.content).strip()
                                if content:
                                    final_content = content

                            elif isinstance(message, ToolMessage):
                                tool_name = message.name or "unknown"
                                result = _content_to_str(message.content)
                                yield {
                                    "tool_result": {
                                        "id": message.tool_call_id,
                                        "name": tool_name,
                                        "result": result,
                                    }
                                }

                                scene_action = _maybe_parse_scene_action(tool_name, result)
                                if scene_action:
                                    yield {"scene_action": scene_action}

                                if tool_name == "rag_search":
                                    buffer = get_rag_sources_buffer() or []
                                    new_sources = buffer[emitted_source_count:]
                                    if new_sources:
                                        yield {"sources": new_sources}
                                        emitted_source_count = len(buffer)
                break
            except Exception as exc:
                if (
                    not emitted_any
                    and is_retryable_api_error(exc)
                    and run_attempt < max_attempts
                ):
                    yield {
                        "retry": {
                            "attempt": run_attempt,
                            "max_attempts": max_attempts,
                            "message": "Scene Agent 调用暂时失败，正在重试…",
                        }
                    }
                    continue
                raise

        if final_content:
            yield {"content": final_content}
        elif not usage_totals["total_tokens"]:
            yield {"error": "Scene Agent 未返回有效回答"}

        if usage_totals["total_tokens"] > 0:
            yield {"usage": usage_totals}

    except GraphRecursionError as exc:
        yield {
            "error": (
                f"超过最大 Agent 迭代次数（{agent_config.agent_max_iterations}）: {exc}"
            )
        }
    except Exception as exc:
        raise AgentRunError(f"Scene Agent 运行失败: {exc}") from exc
