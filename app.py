from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from agent import has_llm_credentials
from chat_backend import LOAD_MORE_COMMAND, initial_ui_state, run_turn, selection_message


st.set_page_config(
    page_title="Vinmec",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f7fbff;
            --bg-soft: #eaf4ff;
            --panel: rgba(255, 255, 255, 0.96);
            --panel-strong: #ffffff;
            --ink: #103450;
            --muted: #64829a;
            --primary: #7bbcff;
            --primary-soft: #d9edff;
            --primary-deep: #2c76b7;
            --line: rgba(44, 118, 183, 0.14);
            --shadow: 0 22px 54px rgba(37, 108, 173, 0.10);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(123, 188, 255, 0.18), transparent 32%),
                linear-gradient(180deg, var(--bg-soft) 0%, var(--bg) 48%, #ffffff 100%);
            color: var(--ink);
            font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        }

        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2rem;
        }

        [data-testid="stSidebar"] {
            background: rgba(245, 250, 255, 0.98);
            border-right: 1px solid var(--line);
        }

        .vm-shell {
            position: relative;
            overflow: hidden;
            border-radius: 26px;
            padding: 18px 22px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.96), rgba(234,244,255,0.98));
            border: 1px solid rgba(123, 188, 255, 0.32);
            box-shadow: var(--shadow);
            animation: riseIn 520ms ease-out;
            margin-bottom: 1rem;
        }

        .vm-brand {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 10px 14px;
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(123, 188, 255, 0.16), rgba(255,255,255,0.95));
            border: 1px solid rgba(123, 188, 255, 0.26);
            width: fit-content;
        }

        .vm-brand-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--primary-deep);
            box-shadow: 0 0 0 5px rgba(123, 188, 255, 0.18);
        }

        .vm-brand-title {
            font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
            font-size: 1.5rem;
            line-height: 1;
            margin: 0;
            color: var(--ink);
        }

        .vm-brand-subtitle {
            margin: 2px 0 0;
            color: var(--muted);
            font-size: 0.92rem;
        }

        .vm-note, .vm-card, .vm-confirm, .vm-success, .vm-sidebar-box {
            background: var(--panel);
            border: 1px solid rgba(123, 188, 255, 0.16);
            box-shadow: var(--shadow);
            animation: riseIn 420ms ease-out;
        }

        .vm-note {
            border-radius: 22px;
            padding: 16px 18px;
            margin-bottom: 1rem;
            color: var(--muted);
        }

        .vm-card {
            border-radius: 22px;
            padding: 18px;
            min-height: 205px;
            margin-bottom: 0.65rem;
        }

        .vm-card h3, .vm-confirm h3, .vm-success h3 {
            font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
            margin: 0 0 0.4rem;
            color: var(--ink);
        }

        .vm-kicker {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--primary-deep);
            margin-bottom: 0.65rem;
        }

        .vm-meta {
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 0.8rem;
        }

        .vm-price {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-weight: 700;
            color: var(--primary-deep);
            background: rgba(123, 188, 255, 0.14);
            border-radius: 999px;
            padding: 8px 12px;
            font-size: 0.92rem;
        }

        .vm-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 0.9rem;
        }

        .vm-chip {
            display: inline-flex;
            align-items: center;
            padding: 7px 12px;
            border-radius: 999px;
            background: rgba(123, 188, 255, 0.14);
            color: var(--primary-deep);
            font-size: 0.86rem;
        }

        .vm-confirm, .vm-success {
            border-radius: 24px;
            padding: 20px;
            margin-bottom: 0.8rem;
        }

        .vm-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-top: 0.85rem;
        }

        .vm-field {
            background: linear-gradient(180deg, #ffffff 0%, #f5faff 100%);
            border: 1px solid rgba(123, 188, 255, 0.18);
            border-radius: 16px;
            padding: 12px 14px;
        }

        .vm-field span {
            display: block;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted);
            margin-bottom: 0.25rem;
        }

        .vm-field strong {
            color: var(--ink);
        }

        .vm-success {
            background:
                linear-gradient(145deg, rgba(123,188,255,0.16), rgba(255,255,255,0.95)),
                rgba(255,255,255,0.94);
        }

        .vm-rating {
            color: var(--primary-deep);
            letter-spacing: 0.25rem;
            font-size: 1.15rem;
            margin-top: 0.35rem;
        }

        .vm-sidebar-box {
            border-radius: 22px;
            padding: 18px;
            margin-bottom: 0.9rem;
        }

        .vm-step {
            padding: 9px 0;
            border-bottom: 1px solid rgba(15, 118, 110, 0.09);
            color: var(--ink);
        }

        .vm-step:last-child {
            border-bottom: none;
        }

        .vm-empty-sidebar {
            height: 1rem;
        }

        .stChatMessage {
            background: transparent;
        }

        .stButton > button {
            width: 100%;
            border-radius: 999px;
            border: none;
            padding: 0.72rem 1rem;
            font-weight: 700;
            background: linear-gradient(135deg, #8ac6ff, #2c76b7);
            color: white;
            box-shadow: 0 12px 26px rgba(44, 118, 183, 0.22);
            transition: transform 120ms ease, box-shadow 120ms ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 16px 34px rgba(44, 118, 183, 0.28);
        }

        .stTextInput input, .stChatInput input {
            border-radius: 16px !important;
        }

        @keyframes riseIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session_state() -> None:
    if "graph_messages" not in st.session_state:
        st.session_state.graph_messages = []
    if "ui_state" not in st.session_state:
        st.session_state.ui_state = initial_ui_state()
    if "chat_entries" not in st.session_state:
        st.session_state.chat_entries = [
            {
                "role": "assistant",
                "text": "Xin chào. Tôi là trợ lý AI y tế của Vinmec. Để bắt đầu xác thực, vui lòng cho tôi số điện thoại của bạn.",
                "components": [],
                "raw": "",
            }
        ]


def clean_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", (text or "").strip())


def format_price(value: Any) -> str:
    if isinstance(value, int):
        return f"{value:,} VNĐ"
    if isinstance(value, str) and value.isdigit():
        return f"{int(value):,} VNĐ"
    return str(value)


def parse_confirm_payload(raw_tag: str) -> dict[str, Any]:
    match = re.search(r"<UI_CONFIRM>(.*?)</UI_CONFIRM>", raw_tag, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def queue_message(message: str, visible: bool = True, display_text: str | None = None) -> None:
    st.session_state.pending_user_message = message
    st.session_state.pending_user_visible = visible
    st.session_state.pending_user_display_text = display_text
    st.rerun()


def process_pending_message() -> None:
    pending_message = st.session_state.pop("pending_user_message", None)
    if pending_message is None:
        return

    visible = st.session_state.pop("pending_user_visible", True)
    display_text = st.session_state.pop("pending_user_display_text", None)
    if visible:
        st.session_state.chat_entries.append(
            {
                "role": "user",
                "text": display_text or pending_message,
                "components": [],
                "raw": pending_message,
            }
        )

    try:
        graph_messages, parsed_response, ui_state = run_turn(
            st.session_state.graph_messages,
            pending_message,
            st.session_state.ui_state,
        )
        st.session_state.graph_messages = graph_messages
        st.session_state.ui_state = ui_state
        st.session_state.chat_entries.append(
            {
                "role": "assistant",
                "text": parsed_response.get("text", ""),
                "components": parsed_response.get("components", []),
                "raw": parsed_response.get("raw", ""),
            }
        )
    except Exception as exc:  # pragma: no cover - UI fallback
        st.session_state.chat_entries.append(
            {
                "role": "assistant",
                "text": f"Không thể xử lý yêu cầu lúc này: {exc}",
                "components": [],
                "raw": "",
            }
        )

    st.rerun()


def render_sidebar() -> None:
    ui_state = st.session_state.ui_state
    booking_result = ui_state.get("last_booking_result") or {}
    confirm_payload = parse_confirm_payload(ui_state.get("last_confirm_tag", ""))

    if confirm_payload:
        patient = confirm_payload.get("patient", {})
        consultation = confirm_payload.get("consultation", {})
        chips = [
            patient.get("full_name") or "Chưa có tên",
            consultation.get("specialty") or "Chưa có chuyên khoa",
            consultation.get("facility") or "Chưa có cơ sở",
        ]
        chip_html = "".join(f'<div class="vm-chip">{chip}</div>' for chip in chips if chip)
        st.sidebar.markdown(
            f"""
            <div class="vm-sidebar-box">
                <div class="vm-kicker">Đang chờ xác nhận</div>
                <div class="vm-chip-row">{chip_html}</div>
                <div class="vm-meta">Thời gian dự kiến: {consultation.get('appointment_time') or 'Chưa chọn'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if booking_result.get("status") == "success":
        st.sidebar.markdown(
            f"""
            <div class="vm-sidebar-box">
                <div class="vm-kicker">Lịch hẹn</div>
                <div class="vm-meta">Mã lịch hẹn: #{booking_result.get('appointment_id')}</div>
                <div class="vm-meta">Bác sĩ: {booking_result.get('doctor')}</div>
                <div class="vm-meta">Thời gian: {booking_result.get('time')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not confirm_payload and not booking_result:
        st.sidebar.markdown('<div class="vm-empty-sidebar"></div>', unsafe_allow_html=True)

    if not has_llm_credentials():
        st.sidebar.warning("Thiếu token model trong `.env`.")


def render_text_block(text: str) -> None:
    if not text:
        return
    st.markdown(
        f'<div class="vm-note">{clean_text(text).replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True,
    )


def render_facility_cards(payload: dict[str, Any], message_index: int) -> None:
    items = payload.get("items", [])
    if not items:
        return

    columns = st.columns(len(items))
    for index, item in enumerate(items):
        with columns[index]:
            st.markdown(
                f"""
                <div class="vm-card">
                    <div class="vm-kicker">Cơ sở Vinmec</div>
                    <h3>{item.get("name", "")}</h3>
                    <div class="vm-meta">{item.get("address", "")}</div>
                    <div class="vm-chip-row">
                        <div class="vm-chip">ID #{item.get("id")}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Chọn cơ sở", key=f"facility-{message_index}-{item.get('id')}"):
                queue_message(
                    selection_message("facilities", item),
                    display_text=f"Đã chọn cơ sở: {item.get('name', '')}",
                )

    if payload.get("has_more"):
        if st.button("Xem thêm cơ sở", key=f"facility-more-{message_index}"):
            queue_message(LOAD_MORE_COMMAND, visible=False)


def render_doctor_cards(payload: dict[str, Any], message_index: int) -> None:
    items = payload.get("items", [])
    if not items:
        return

    columns = st.columns(len(items))
    for index, item in enumerate(items):
        with columns[index]:
            st.markdown(
                f"""
                <div class="vm-card">
                    <div class="vm-kicker">Bác sĩ phù hợp</div>
                    <h3>{item.get("name", "")}</h3>
                    <div class="vm-meta">{item.get("degree", "Chưa cập nhật học hàm/học vị")}</div>
                    <div class="vm-price">Chi phí tham khảo: {format_price(item.get("price", ""))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Chọn bác sĩ", key=f"doctor-{message_index}-{item.get('id')}"):
                queue_message(
                    selection_message("doctors", item),
                    display_text=f"Đã chọn bác sĩ: {item.get('name', '')}",
                )

    if payload.get("has_more"):
        if st.button("Xem thêm bác sĩ", key=f"doctor-more-{message_index}"):
            queue_message(LOAD_MORE_COMMAND, visible=False)


def render_slot_cards(payload: dict[str, Any], message_index: int) -> None:
    items = payload.get("items", [])
    if not items:
        return

    columns = st.columns(len(items))
    for index, item in enumerate(items):
        with columns[index]:
            st.markdown(
                f"""
                <div class="vm-card">
                    <div class="vm-kicker">Khung giờ khám</div>
                    <h3>{item.get("time", "")}</h3>
                    <div class="vm-chip-row">
                        <div class="vm-chip">Slot #{item.get("id")}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Chọn giờ khám", key=f"slot-{message_index}-{item.get('id')}"):
                queue_message(
                    selection_message("slots", item),
                    display_text=f"Đã chọn giờ khám: {item.get('time', '')}",
                )

    if payload.get("has_more"):
        if st.button("Xem thêm giờ khám", key=f"slot-more-{message_index}"):
            queue_message(LOAD_MORE_COMMAND, visible=False)


def render_confirm_card(raw_tag: str, message_index: int) -> None:
    payload = parse_confirm_payload(raw_tag)
    if not payload:
        return

    patient = payload.get("patient", {})
    consultation = payload.get("consultation", {})

    st.markdown(
        f"""
        <div class="vm-confirm">
            <div class="vm-kicker">Xác nhận thông tin</div>
            <h3>Kiểm tra lại trước khi tạo lịch hẹn</h3>
            <div class="vm-grid">
                <div class="vm-field"><span>Họ tên</span><strong>{patient.get("full_name") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Số điện thoại</span><strong>{patient.get("phone") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Giới tính</span><strong>{patient.get("gender") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Email</span><strong>{patient.get("email") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Ngày sinh</span><strong>{patient.get("date_of_birth") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Triệu chứng</span><strong>{consultation.get("symptom_summary") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Chuyên khoa</span><strong>{consultation.get("specialty") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Cơ sở</span><strong>{consultation.get("facility") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Bác sĩ</span><strong>{consultation.get("doctor") or "Chưa cập nhật"}</strong></div>
                <div class="vm-field"><span>Thời gian</span><strong>{consultation.get("appointment_time") or "Chưa cập nhật"}</strong></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    confirm_message = (
        "Tôi xác nhận đặt lịch với các thông tin vừa tóm tắt."
        f" slot_id={consultation.get('slot_id') or ''}"
        f" họ_tên={patient.get('full_name') or ''}"
        f" số_điện_thoại={patient.get('phone') or ''}"
    )
    if st.button("Xác nhận và tạo lịch", key=f"confirm-{message_index}"):
        queue_message(confirm_message, display_text="Tôi xác nhận thông tin đặt lịch.")


def render_rating_success(message_index: int) -> None:
    booking_result = st.session_state.ui_state.get("last_booking_result") or {}
    st.markdown(
        f"""
        <div class="vm-success">
            <div class="vm-kicker">Đặt lịch thành công</div>
            <h3>Lịch hẹn của bạn đã được ghi nhận</h3>
            <div class="vm-meta">
                Mã lịch hẹn: #{booking_result.get("appointment_id", "N/A")}<br>
                Bác sĩ: {booking_result.get("doctor", "Đang cập nhật")}<br>
                Thời gian: {booking_result.get("time", "Đang cập nhật")}
            </div>
            <div class="vm-rating">★★★★★</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_component(component: dict[str, Any], message_index: int) -> None:
    tag = component.get("tag")
    payload = component.get("payload")

    if tag == "UI_FACILITIES" and isinstance(payload, dict):
        render_facility_cards(payload, message_index)
    elif tag == "UI_DOCTORS" and isinstance(payload, dict):
        render_doctor_cards(payload, message_index)
    elif tag == "UI_SLOTS" and isinstance(payload, dict):
        render_slot_cards(payload, message_index)
    elif tag == "UI_CONFIRM":
        render_confirm_card(component.get("raw", ""), message_index)
    elif tag == "UI_RATING":
        render_rating_success(message_index)


def render_chat_history() -> None:
    for index, entry in enumerate(st.session_state.chat_entries):
        role = entry.get("role", "assistant")
        with st.chat_message("assistant" if role == "assistant" else "user"):
            render_text_block(entry.get("text", ""))
            for component in entry.get("components", []):
                render_component(component, index)


def render_header() -> None:
    st.markdown(
        """
        <div class="vm-shell">
            <div class="vm-brand">
                <div class="vm-brand-dot"></div>
                <div>
                    <div class="vm-brand-title">Vinmec</div>
                    <div class="vm-brand-subtitle">Trợ lý đặt lịch khám</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_styles()
    init_session_state()
    process_pending_message()
    render_sidebar()
    render_header()
    render_chat_history()

    user_prompt = st.chat_input("Nhập triệu chứng, nhu cầu đặt lịch hoặc số điện thoại của bạn...")
    if user_prompt:
        queue_message(user_prompt)


if __name__ == "__main__":
    main()
