from __future__ import annotations

import json
import math
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(func):
        return func


ROOT_DIR = Path(__file__).resolve().parent
DB_CANDIDATES = [
    ROOT_DIR / "data" / "vinmec.sqlite",
    ROOT_DIR / "vinmec.sqlite3",
]

DB_PATH = None
for path in DB_CANDIDATES:
    if path.exists():
        DB_PATH = path
        break

if DB_PATH is None:
    raise FileNotFoundError("Database file not found")

@tool
def get_doctor_schedule(doctor_name: str) -> str:
    """
    Trả về lịch làm việc của bác sĩ dựa trên tên.
    Input: tên bác sĩ (nhập đúng và đủ tên bác sĩ, tiếng Việt)
    Output: danh sách ca làm việc với trạng thái slot còn trống hay đã đặt
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tìm bác sĩ khớp tên (không phân biệt hoa thường)
    cursor.execute("""
        SELECT DISTINCT d.doctor_id, d.full_name
        FROM doctors d
        WHERE d.full_name LIKE ? OR d.normalized_name LIKE ?
    """, (f"%{doctor_name}%", f"%{doctor_name}%"))

    doctors = cursor.fetchall()

    if not doctors:
        conn.close()
        return f"Không tìm thấy bác sĩ nào có tên '{doctor_name}'."

    result = []

    for doctor_id, full_name in doctors:
        result.append(f"📅 Lịch làm việc của bác sĩ {full_name}:\n")

        cursor.execute("""
            SELECT ds.work_date, ds.shift, ds.start_at, ds.end_at, ds.status,
                   COUNT(s.slot_id) as total_slots,
                   SUM(CASE WHEN s.status = 'available' THEN 1 ELSE 0 END) as available_slots
            FROM doctor_schedules ds
            LEFT JOIN doctor_schedule_slots s ON s.schedule_id = ds.schedule_id
            WHERE ds.doctor_id = ?
            GROUP BY ds.schedule_id
            ORDER BY ds.work_date, ds.start_at
        """, (doctor_id,))

        schedules = cursor.fetchall()

        if not schedules:
            result.append("  Không có lịch làm việc.\n")
            continue

        for row in schedules:
            work_date, shift, start_at, end_at, status, total, available = row
            available = available or 0
            booked = total - available
            slot_status = "✅ Còn chỗ" if available > 0 else "❌ Hết chỗ"
            result.append(
                f"  - Ngày: {work_date} | Ca: {shift} "
                f"| Giờ: {start_at} - {end_at} "
                f"| Còn trống: {available}/{total} (Đã đặt: {booked}) "
                f"| {slot_status}"
            )

        result.append("")

    conn.close()
    return "\n".join(result)

from langchain_core.tools import tool

@tool
def confirm_appointment_summary(
    full_name: str,
    phone: str,
    specialty: str,
    facility: str,
    preferred_time: str,
    note: str = ""
) -> str:
    """
    Tóm tắt thông tin đặt lịch khám của bệnh nhân trước khi xác nhận.
    Dùng khi đã thu thập đủ thông tin từ người dùng để chốt lịch hẹn.

    Args:
        full_name: Họ tên đầy đủ của bệnh nhân
        phone: Số điện thoại liên hệ
        specialty: Chuyên khoa hoặc dịch vụ muốn khám
        facility: Cơ sở Vinmec mong muốn
        preferred_time: Thời gian mong muốn đặt lịch
        note: Ghi chú thêm (triệu chứng, yêu cầu đặc biệt,...)
    """
    # Kiểm tra các trường bắt buộc
    missing = []
    if not full_name.strip():
        missing.append("Họ tên")
    if not phone.strip():
        missing.append("Số điện thoại")
    if not specialty.strip():
        missing.append("Chuyên khoa/dịch vụ")
    if not facility.strip():
        missing.append("Cơ sở Vinmec")
    if not preferred_time.strip():
        missing.append("Thời gian mong muốn")

    if missing:
        return (
            f"⚠️ Còn thiếu thông tin sau để hoàn tất đặt lịch:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nVui lòng cung cấp thêm để tiếp tục."
        )

    summary = f"""
✅ Xác nhận thông tin đặt lịch khám tại Vinmec:

- Họ tên:               {full_name}
- Số điện thoại:        {phone}
- Chuyên khoa/dịch vụ: {specialty}
- Cơ sở Vinmec:        {facility}
- Thời gian mong muốn: {preferred_time}
- Ghi chú:             {note if note.strip() else "Không có"}

📌 Vui lòng xác nhận lại thông tin trên. Nếu chính xác, chúng tôi sẽ tiến hành đặt lịch cho bạn.
"""
    return summary.strip()



@tool
def book_appointment(
    full_name: str,
    phone: str,
    specialty: str,
    facility: str,
    preferred_date: str,
    shift: str,
    symptom_text: str = "",
    nationality_type: str = "local"
) -> str:
    """
    Đặt lịch khám và cập nhật database khi user xác nhận.
    Tìm slot trống phù hợp → tạo user nếu chưa có → tạo appointment → cập nhật slot.

    Args:
        full_name: Họ tên bệnh nhân
        phone: Số điện thoại
        specialty: Tên chuyên khoa
        facility: Tên cơ sở Vinmec
        preferred_date: Ngày muốn khám (YYYY-MM-DD)
        shift: Ca khám (morning/afternoon)
        symptom_text: Triệu chứng hoặc ghi chú
        nationality_type: 'local' hoặc 'foreign'
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # ── 1. Tìm facility ──────────────────────────────────────────
        cursor.execute("""
            SELECT facility_id, name FROM facilities
            WHERE name LIKE ? OR normalized_name LIKE ?
            LIMIT 1
        """, (f"%{facility}%", f"%{facility.lower()}%"))
        facility_row = cursor.fetchone()
        if not facility_row:
            return f"❌ Không tìm thấy cơ sở Vinmec: '{facility}'"
        facility_id = facility_row["facility_id"]
        facility_name = facility_row["name"]

        # ── 2. Tìm specialty ─────────────────────────────────────────
        cursor.execute("""
            SELECT specialty_id, name FROM specialties
            WHERE name LIKE ? OR normalized_name LIKE ?
            LIMIT 1
        """, (f"%{specialty}%", f"%{specialty.lower()}%"))
        specialty_row = cursor.fetchone()
        specialty_id = specialty_row["specialty_id"] if specialty_row else None

        # ── 3. Tìm slot available ────────────────────────────────────
        cursor.execute("""
            SELECT
                s.slot_id, s.schedule_id, s.doctor_id,
                s.slot_date, s.start_at, s.end_at,
                d.full_name as doctor_name,
                d.price_local, d.price_foreigner
            FROM doctor_schedule_slots s
            JOIN doctor_schedules ds ON s.schedule_id = ds.schedule_id
            JOIN doctors d ON s.doctor_id = d.doctor_id
            WHERE s.slot_date = ?
              AND ds.shift = ?
              AND ds.facility_id = ?
              AND s.status = 'available'
            ORDER BY s.start_at
            LIMIT 1
        """, (preferred_date, shift, facility_id))
        slot = cursor.fetchone()

        if not slot:
            return (
                f"❌ Không còn slot trống vào ngày {preferred_date} "
                f"ca {shift} tại {facility_name}.\n"
                f"Vui lòng chọn ngày hoặc ca khác."
            )

        slot_id     = slot["slot_id"]
        doctor_id   = slot["doctor_id"]
        doctor_name = slot["doctor_name"]
        fee = slot["price_local"] if nationality_type == "local" else slot["price_foreigner"]

        # ── 4. Tạo / lấy user ───────────────────────────────────────
        cursor.execute("""
            SELECT user_id FROM users WHERE phone = ? LIMIT 1
        """, (phone,))
        user_row = cursor.fetchone()

        if user_row:
            user_id = user_row["user_id"]
        else:
            cursor.execute("""
                INSERT INTO users (full_name, phone, nationality_type)
                VALUES (?, ?, ?)
            """, (full_name, phone, nationality_type))
            user_id = cursor.lastrowid

        # ── 5. Tạo appointment ───────────────────────────────────────
        cursor.execute("""
            INSERT INTO appointments (
                user_id, doctor_id, facility_id, specialty_id,
                slot_id, symptom_text, nationality_type,
                consultation_fee, status, confirmed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', CURRENT_TIMESTAMP)
        """, (
            user_id, doctor_id, facility_id, specialty_id,
            slot_id, symptom_text, nationality_type, fee
        ))
        appointment_id = cursor.lastrowid

        # ── 6. Cập nhật slot → booked ────────────────────────────────
        cursor.execute("""
            UPDATE doctor_schedule_slots
            SET status = 'booked'
            WHERE slot_id = ?
        """, (slot_id,))

        conn.commit()

        return f"""
✅ Đặt lịch thành công! Mã lịch hẹn: #{appointment_id}

📋 Thông tin xác nhận:
- Họ tên:          {full_name}
- Số điện thoại:   {phone}
- Bác sĩ:          {doctor_name}
- Chuyên khoa:     {specialty}
- Cơ sở Vinmec:    {facility_name}
- Ngày khám:       {slot['slot_date']}
- Giờ khám:        {slot['start_at']} - {slot['end_at']}
- Chi phí:         {fee:,} VNĐ
- Triệu chứng:     {symptom_text or 'Không có'}

📌 Vui lòng đến trước giờ hẹn 15 phút và mang theo CMND/CCCD.
""".strip()

    except Exception as e:
        conn.rollback()
        return f"❌ Lỗi khi đặt lịch: {str(e)}"

    finally:
        conn.close()


tools_list = [get_doctor_schedule, confirm_appointment_summary, book_appointment]
