from __future__ import annotations

import json
import re
from typing import Any

from agent import get_graph


LOAD_MORE_COMMAND = "LỆNH_HỆ_THỐNG: Tải thêm 3 kết quả tiếp theo"
TAG_PATTERN = re.compile(r"<(UI_[A-Z_]+)>(.*?)</\1>", re.DOTALL)

TOOL_TO_COMPONENT = {
    "get_hospital_locations": "facilities",
    "get_suitable_availability_doctor": "doctors",
    "get_suitable_availibility_doctor": "doctors",
    "get_doctor_by_specialty": "doctors",
    "check_availability": "slots",
}

COMPONENT_TO_TAG = {
    "facilities": "UI_FACILITIES",
    "doctors": "UI_DOCTORS",
    "slots": "UI_SLOTS",
}


def initial_ui_state() -> dict[str, Any]:
    return {
        "facilities": {"items": [], "offset": 0},
        "doctors": {"items": [], "offset": 0},
        "slots": {"items": [], "offset": 0},
        "active_component": None,
        "last_confirm_tag": "",
        "last_booking_result": None,
    }


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
                continue
            if isinstance(chunk, dict):
                if chunk.get("type") == "text":
                    parts.append(chunk.get("text", ""))
                elif "text" in chunk:
                    parts.append(str(chunk["text"]))
        return "\n".join(part for part in parts if part).strip()
    return str(content or "")


def _safe_json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


def _format_component_items(component: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if component == "facilities":
        return [
            {
                "id": int(item.get("id", item.get("facility_id"))),
                "name": item["name"],
                "address": item.get("address", ""),
            }
            for item in items
        ]
    if component == "doctors":
        return [
            {
                "id": int(item.get("id", item.get("doctor_id"))),
                "name": item["name"],
                "degree": item.get("degree", item.get("experience", "")),
                "price": item.get("price", ""),
            }
            for item in items
        ]
    if component == "slots":
        return [
            {
                "id": int(item["id"]),
                "time": item["time"],
            }
            for item in items
        ]
    return items


def build_component_tag(component: str, items: list[dict[str, Any]], start: int = 0, page_size: int = 3) -> str:
    chunk = _format_component_items(component, items[start:start + page_size])
    payload = {
        "has_more": len(items) > start + len(chunk),
        "items": chunk,
    }
    tag_name = COMPONENT_TO_TAG[component]
    return f"<{tag_name}>{json.dumps(payload, ensure_ascii=False)}</{tag_name}>"


def _sync_ui_state(ui_state: dict[str, Any], new_messages: list[Any]) -> dict[str, Any]:
    for message in new_messages:
        tool_name = getattr(message, "name", "")
        if tool_name in TOOL_TO_COMPONENT:
            payload = _safe_json_loads(_extract_text(message.content)) or {}
            items = payload if isinstance(payload, list) else payload.get("items", [])
            if isinstance(items, list):
                component = TOOL_TO_COMPONENT[tool_name]
                ui_state[component] = {"items": items, "offset": min(3, len(items))}
                if items:
                    ui_state["active_component"] = component
        elif tool_name == "summarize_consultation":
            confirm_tag = _extract_text(message.content).strip()
            if confirm_tag.startswith("<UI_CONFIRM>"):
                ui_state["last_confirm_tag"] = confirm_tag
        elif tool_name == "create_consultation":
            payload = _safe_json_loads(_extract_text(message.content))
            if isinstance(payload, dict):
                ui_state["last_booking_result"] = payload
    return ui_state


def _append_missing_ui_tags(response_text: str, ui_state: dict[str, Any], new_messages: list[Any]) -> str:
    additions: list[str] = []
    latest_component: str | None = None

    for message in new_messages:
        tool_name = getattr(message, "name", "")
        if tool_name in TOOL_TO_COMPONENT:
            latest_component = TOOL_TO_COMPONENT[tool_name]
        elif tool_name == "summarize_consultation":
            confirm_tag = _extract_text(message.content).strip()
            if confirm_tag.startswith("<UI_CONFIRM>") and "<UI_CONFIRM>" not in response_text:
                additions.append(confirm_tag)
        elif tool_name == "create_consultation":
            booking_payload = _safe_json_loads(_extract_text(message.content)) or {}
            if booking_payload.get("status") == "success" and "<UI_RATING>" not in response_text:
                if not response_text.strip():
                    response_text = "Đặt lịch thành công."
                additions.append('<UI_RATING>{"status": "success"}</UI_RATING>')

    if latest_component and COMPONENT_TO_TAG[latest_component] not in response_text:
        items = ui_state[latest_component]["items"]
        if items:
            additions.append(build_component_tag(latest_component, items, start=0))

    if additions:
        response_text = response_text.rstrip()
        if response_text:
            response_text = response_text + "\n" + "\n".join(additions)
        else:
            response_text = "\n".join(additions)
    return response_text


def parse_assistant_content(content: str) -> dict[str, Any]:
    components: list[dict[str, Any]] = []

    def _replace_tag(match: re.Match[str]) -> str:
        tag_name = match.group(1)
        inner = match.group(2).strip()
        payload = _safe_json_loads(inner)
        components.append({"tag": tag_name, "payload": payload, "raw": match.group(0)})
        return ""

    text = TAG_PATTERN.sub(_replace_tag, content).strip()
    return {"text": text, "components": components, "raw": content}


def render_more(ui_state: dict[str, Any]) -> dict[str, Any]:
    component = ui_state.get("active_component")
    if component not in COMPONENT_TO_TAG:
        return parse_assistant_content("")

    items = ui_state[component]["items"]
    offset = int(ui_state[component]["offset"])
    if offset >= len(items):
        return parse_assistant_content("")

    raw = build_component_tag(component, items, start=offset)
    ui_state[component]["offset"] = min(offset + 3, len(items))
    return parse_assistant_content(raw)


def selection_message(component: str, item: dict[str, Any]) -> str:
    if component == "facilities":
        return (
            f"Tôi chọn cơ sở {item['name']} (facility_id={item['id']}). "
            "Nếu đã đủ chuyên khoa, ngày và ca khám thì hãy hiển thị ngay danh sách bác sĩ tiếp theo bằng UI_DOCTORS."
        )
    if component == "doctors":
        return (
            f"Tôi chọn bác sĩ {item['name']} (doctor_id={item['id']}). "
            "Hãy hiển thị ngay các giờ khám còn trống tiếp theo bằng UI_SLOTS."
        )
    if component == "slots":
        return (
            f"Tôi chọn giờ khám {item['time']} (slot_id={item['id']}). "
            "Hãy chuyển sang bước tóm tắt xác nhận đặt lịch."
        )
    return str(item)


def run_turn(messages: list[Any], user_text: str, ui_state: dict[str, Any]) -> tuple[list[Any], dict[str, Any], dict[str, Any]]:
    stripped_text = user_text.strip()
    if stripped_text == LOAD_MORE_COMMAND:
        return messages, render_more(ui_state), ui_state

    graph = get_graph()
    previous_length = len(messages)
    result = graph.invoke({"messages": messages + [("human", user_text)]})
    updated_messages = result["messages"]
    new_messages = updated_messages[previous_length:]
    ui_state = _sync_ui_state(ui_state, new_messages)

    final_text = _extract_text(updated_messages[-1].content)
    final_text = _append_missing_ui_tags(final_text, ui_state, new_messages)
    parsed_content = parse_assistant_content(final_text)
    return updated_messages, parsed_content, ui_state
