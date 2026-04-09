from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(func):
        return func


ROOT_DIR = Path(__file__).resolve().parent
_DB_OVERRIDE = os.getenv("VINMEC_DB_PATH")
DB_CANDIDATES = [
    Path(_DB_OVERRIDE).expanduser().resolve() if _DB_OVERRIDE else None,
    ROOT_DIR / "data" / "vinmec.sqlite",
    ROOT_DIR / "vinmec.sqlite3",
]

SHIFT_ALIASES = {
    "morning": "morning",
    "sang": "morning",
    "buoi sang": "morning",
    "afternoon": "afternoon",
    "chieu": "afternoon",
    "buoi chieu": "afternoon",
    "evening": "evening",
    "toi": "evening",
    "buoi toi": "evening",
    "full_day": "full_day",
    "ca ngay": "full_day",
    "all day": "full_day",
    "custom": "custom",
}

KNOWN_LOCATIONS = {
    "vinuni": (21.0393, 105.9380),
    "vin uni": (21.0393, 105.9380),
    "vin university": (21.0393, 105.9380),
    "gia lam": (21.0408, 105.9385),
    "ha noi": (21.0285, 105.8542),
    "hanoi": (21.0285, 105.8542),
    "ho chi minh": (10.7769, 106.7009),
    "hcm": (10.7769, 106.7009),
    "sai gon": (10.7769, 106.7009),
}

SPECIALTY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("Khám sức khỏe tổng quát người lớn", ("kham tong quat", "check up", "dinh ky", "tong quat")),
    ("Tim mạch", ("dau nguc", "tim", "hoi hop", "tang huyet ap", "mach")),
    ("Da liễu", ("da", "ngua", "mun", "phat ban", "di ung da")),
    ("Nội tiết", ("tuyen giap", "noi tiet", "duong huyet", "tieu duong")),
    ("Tai mũi họng", ("tai", "mui", "hong", "viem hong")),
    ("Tiêu hóa", ("da day", "tieu hoa", "dau bung", "trao nguoc")),
    ("Cơ xương khớp", ("xuong", "khop", "lung", "co vai gay")),
    ("Thần kinh", ("dau dau", "te", "chon mat", "mat ngu", "than kinh")),
    ("Hô hấp", ("ho", "kho tho", "pho i", "viem phe quan")),
    ("Nhi", ("tre em", "em be", "be bi", "nhi")),
]

EMERGENCY_KEYWORDS = (
    "kho tho",
    "dau nguc du doi",
    "mat y thuc",
    "co giat",
    "liet",
    "dot quy",
    "khong tho duoc",
    "chay mau nhieu",
    "tim dap nhanh bat thuong",
)

REQUIRED_OBJECTS = [
    "users",
    "facilities",
    "specialties",
    "doctors",
    "doctor_specialties",
    "doctor_schedules",
    "doctor_schedule_slots",
    "appointments",
    "vw_available_slots",
]


def _db_has_objects(path: Path, object_names: list[str]) -> bool:
    if not path or not path.exists():
        return False
    try:
        with sqlite3.connect(path) as connection:
            cursor = connection.cursor()
            for name in object_names:
                found = cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name = ?",
                    (name,),
                ).fetchone()
                if not found:
                    return False
            return True
    except sqlite3.Error:
        return False


def _resolve_db_path() -> Path:
    valid_candidates = [candidate for candidate in DB_CANDIDATES if candidate]
    for candidate in valid_candidates:
        if _db_has_objects(candidate, REQUIRED_OBJECTS):
            return candidate
    for candidate in valid_candidates:
        if candidate.exists():
            return candidate
    return ROOT_DIR / "data" / "vinmec.sqlite"


DB_PATH = _resolve_db_path()


def _connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", text).strip().lower()


def _digits_only(value: str | None) -> str:
    return re.sub(r"\D+", "", value or "")


def _normalize_shift(value: str | None) -> str:
    key = _normalize_text(value)
    return SHIFT_ALIASES.get(key, key)


def _normalize_day(day: str | None) -> str:
    text = (day or "").strip()
    if not text:
        return date.today().isoformat()

    normalized = _normalize_text(text)
    if normalized in {"hom nay", "today"}:
        return date.today().isoformat()
    if normalized in {"ngay mai", "tomorrow"}:
        return (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def _format_slot_time(start_at: str, slot_date: str) -> str:
    try:
        start_dt = datetime.fromisoformat(start_at)
    except ValueError:
        start_dt = datetime.strptime(f"{slot_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
    return f"{start_dt.strftime('%H:%M')} ({start_dt.strftime('%d/%m')})"


def _format_slot_window(start_at: str, end_at: str) -> str:
    start_dt = datetime.fromisoformat(start_at)
    end_dt = datetime.fromisoformat(end_at)
    return f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} ({start_dt.strftime('%d/%m/%Y')})"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def _guess_coordinates(location: str | None) -> tuple[float, float] | None:
    text = (location or "").strip()
    if not text:
        return KNOWN_LOCATIONS["vinuni"]

    try:
        lat, lon = map(float, text.split(","))
        return lat, lon
    except ValueError:
        pass

    normalized = _normalize_text(text)
    for key, coords in KNOWN_LOCATIONS.items():
        if key in normalized:
            return coords
    return None


def _infer_specialty(symptom_text: str, fallback: str = "") -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", _normalize_text(symptom_text))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return fallback

    for specialty_name, hints in SPECIALTY_HINTS:
        if any(re.search(rf"(?:^| ){re.escape(hint)}(?: |$)", normalized) for hint in hints):
            return specialty_name
    return fallback


def _to_hhmm(value: str | None) -> str:
    if not value:
        return ""
    return value[:5]


def _resolve_specialty_id(connection: sqlite3.Connection, specialty: str | None) -> tuple[int | None, str]:
    if not specialty:
        return None, ""

    normalized = _normalize_text(specialty)
    row = connection.execute(
        """
        SELECT specialty_id, name
        FROM specialties
        WHERE normalized_name LIKE '%' || ? || '%'
           OR LOWER(name) LIKE '%' || ? || '%'
        ORDER BY CASE WHEN normalized_name = ? THEN 0 ELSE 1 END, name
        LIMIT 1
        """,
        (normalized, specialty.lower(), normalized),
    ).fetchone()
    if not row:
        return None, specialty
    return int(row["specialty_id"]), row["name"]


def _extract_tool_items(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    items = payload.get("items", [])
    return items if isinstance(items, list) else []


def _extract_experience_label(description: str | None, qualification: str | None) -> str:
    joined_text = " ".join(part for part in (description, qualification) if part)
    match = re.search(r"(\d{1,2})\s*n[aă]m kinh nghi[eẹ]m", _normalize_text(joined_text))
    if match:
        return f"{match.group(1)} năm"
    return "Chưa cập nhật"


def _mock_rating_for_doctor(doctor_id: int) -> dict[str, Any]:
    rating = min(4.9, round(4.2 + ((int(doctor_id) * 7) % 8) * 0.1, 1))
    review_count = 40 + (int(doctor_id) * 17 % 180)
    return {"rating": rating, "review_count": review_count, "source": "mock"}


def _future_end_date(days_ahead: int = 30) -> str:
    return (date.today() + timedelta(days=days_ahead)).isoformat()


@tool
def identify_user(phone: str) -> str:
    """Identify an existing patient by phone number before moving to medical triage."""
    normalized_phone = _digits_only(phone)
    if len(normalized_phone) < 9:
        return _json_dumps(
            {
                "status": "invalid",
                "phone": normalized_phone,
                "message": "Số điện thoại không hợp lệ.",
            }
        )

    with _connect_db() as connection:
        row = connection.execute(
            """
            SELECT user_id, full_name, phone, email, date_of_birth, gender, nationality_type
            FROM users
            WHERE phone = ?
            LIMIT 1
            """,
            (normalized_phone,),
        ).fetchone()

    if row is None:
        return _json_dumps(
            {
                "status": "new_user",
                "phone": normalized_phone,
                "message": "Chưa tìm thấy hồ sơ theo số điện thoại này.",
                "user": None,
            }
        )

    return _json_dumps(
        {
            "status": "identified",
            "phone": normalized_phone,
            "message": "Đã xác thực người dùng.",
            "user": {
                "user_id": int(row["user_id"]),
                "full_name": row["full_name"] or "",
                "phone": row["phone"] or normalized_phone,
                "email": row["email"] or "",
                "date_of_birth": row["date_of_birth"] or "",
                "gender": row["gender"] or "",
                "nationality_type": row["nationality_type"] or "local",
            },
        }
    )


@tool
def get_user_profile(phone: str) -> str:
    """Return the saved user profile for a returning patient."""
    normalized_phone = _digits_only(phone)
    if len(normalized_phone) < 9:
        return _json_dumps({"found": False, "message": "Số điện thoại không hợp lệ."})

    with _connect_db() as connection:
        row = connection.execute(
            """
            SELECT full_name, phone, nationality_type, email, date_of_birth, gender
            FROM users
            WHERE phone = ?
            LIMIT 1
            """,
            (normalized_phone,),
        ).fetchone()

    if row is None:
        return _json_dumps({"found": False, "message": "Chưa tìm thấy hồ sơ người dùng."})

    return _json_dumps(
        {
            "found": True,
            "full_name": row["full_name"] or "",
            "phone": row["phone"] or normalized_phone,
            "nationality": row["nationality_type"] or "local",
            "email": row["email"] or "",
            "date_of_birth": row["date_of_birth"] or "",
            "gender": row["gender"] or "",
        }
    )


@tool
def triage_symptom_checker(
    symptom_text: str,
    duration: str = "",
    severity: str = "",
    body_location: str = "",
    accompanying_symptoms: str = "",
    age_or_group: str = "",
    medical_history: str = "",
) -> str:
    """Basic medical triage. Stops the flow when symptoms look emergent."""
    combined_text = " ".join(
        part
        for part in [
            symptom_text,
            duration,
            severity,
            body_location,
            accompanying_symptoms,
            age_or_group,
            medical_history,
        ]
        if part
    )
    normalized = _normalize_text(combined_text)
    is_emergency = any(keyword in normalized for keyword in EMERGENCY_KEYWORDS)
    if _normalize_text(severity) in {"nang", "severe", "rat nang"} and any(
        urgent_word in normalized for urgent_word in ("dau nguc", "kho tho", "ngat", "co giat")
    ):
        is_emergency = True

    specialty = _infer_specialty(combined_text, fallback="Nội tổng quát")
    status = "emergency" if is_emergency else "non_emergency"
    advice = (
        "Có dấu hiệu cần cấp cứu. Hãy gọi 115 hoặc đến cơ sở cấp cứu gần nhất ngay."
        if is_emergency
        else "Chưa ghi nhận dấu hiệu cấp cứu rõ ràng. Có thể tiếp tục đặt lịch khám phù hợp."
    )

    return _json_dumps(
        {
            "status": status,
            "is_emergency": is_emergency,
            "recommended_specialty": specialty,
            "summary": {
                "symptom_text": symptom_text,
                "duration": duration,
                "severity": severity,
                "body_location": body_location,
                "accompanying_symptoms": accompanying_symptoms,
                "age_or_group": age_or_group,
                "medical_history": medical_history,
            },
            "advice": advice,
        }
    )


@tool
def recommend_specialty_from_symptom(symptom_text: str) -> str:
    """Map symptom text to a likely specialty using the local rule set."""
    return _json_dumps(
        {
            "recommended_specialty": _infer_specialty(symptom_text, fallback="Nội tổng quát"),
        }
    )


@tool
def get_hospital_locations(location: str = "", limit: int = 20) -> str:
    """Return Vinmec facilities matching a city, district, address hint, or facility keyword."""
    search = _normalize_text(location)
    limit = max(1, min(int(limit or 20), 50))

    with _connect_db() as connection:
        rows = connection.execute(
            "SELECT facility_id, name, address, province FROM facilities ORDER BY name"
        ).fetchall()

    if not search:
        selected_rows = rows[:limit]
    else:
        scored_rows: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            normalized_name = _normalize_text(row["name"])
            normalized_address = _normalize_text(row["address"] or "")
            normalized_province = _normalize_text(row["province"] or "")

            score = 0
            if search == normalized_name:
                score += 8
            if search in normalized_name:
                score += 5
            if search in normalized_province:
                score += 4
            if search in normalized_address:
                score += 3

            search_tokens = [token for token in search.split() if token]
            if search_tokens and all(
                any(token in field for field in (normalized_name, normalized_address, normalized_province))
                for token in search_tokens
            ):
                score += 2

            if score > 0:
                scored_rows.append((score, row))

        scored_rows.sort(key=lambda item: (-item[0], item[1]["name"]))
        selected_rows = [row for _, row in scored_rows[:limit]]
        if not selected_rows:
            selected_rows = rows[:limit]

    items = [
        {
            "id": int(row["facility_id"]),
            "name": row["name"],
            "address": row["address"] or "",
        }
        for row in selected_rows
    ]
    return _json_dumps(
        {
            "query": location,
            "total": len(items),
            "items": items,
        }
    )


@tool
def get_nearest_branch(location: str = "VinUni, Gia Lam, Ha Noi", max_results: int = 3) -> str:
    """Return nearest facilities using local coordinates when available."""
    max_results = max(1, min(int(max_results or 3), 10))
    coordinates = _guess_coordinates(location)

    with _connect_db() as connection:
        rows = connection.execute(
            """
            SELECT name, latitude, longitude
            FROM facilities
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """
        ).fetchall()

    if not rows:
        return "Khong tim thay toa do chi nhanh trong database."

    if coordinates is None:
        facilities = _extract_tool_items(get_hospital_locations.invoke({"location": location, "limit": max_results}))
        if not facilities:
            return "Khong tim thay co so phu hop."
        return "\n".join(f"{item['name']}: khong co du lieu khoang cach" for item in facilities[:max_results])

    ranked: list[tuple[str, float]] = []
    for row in rows:
        distance = _haversine_km(coordinates[0], coordinates[1], float(row["latitude"]), float(row["longitude"]))
        ranked.append((row["name"], distance))

    ranked.sort(key=lambda item: item[1])
    return "\n".join(f"{name}: {distance:.1f} km" for name, distance in ranked[:max_results])


@tool
def search_doctor_availability_range(
    start_date: str,
    end_date: str,
    specialty: str = "",
    facility: str = "",
    shift: str = "",
    limit: int = 100,
) -> str:
    """Find doctor availability across a date range without looping day-by-day."""
    normalized_start = _normalize_day(start_date)
    normalized_end = _normalize_day(end_date)
    normalized_shift = _normalize_shift(shift)
    specialty_filter = _normalize_text(specialty)
    facility_filter = _normalize_text(facility)
    limit = max(1, min(int(limit or 100), 200))

    query = """
    SELECT
        v.slot_date AS date,
        sch.shift,
        COUNT(DISTINCT v.slot_id) AS available_slots,
        d.doctor_id,
        d.full_name AS doctor_name,
        MIN(time(v.start_at)) AS start_time,
        MAX(time(v.end_at)) AS end_time,
        f.facility_id,
        f.name AS facility_name
    FROM vw_available_slots v
    JOIN doctor_schedules sch
      ON sch.schedule_id = v.schedule_id
    JOIN doctors d
      ON d.doctor_id = v.doctor_id
    JOIN facilities f
      ON f.facility_id = v.facility_id
    LEFT JOIN doctor_specialties ds
      ON ds.doctor_id = d.doctor_id
    LEFT JOIN specialties sp
      ON sp.specialty_id = ds.specialty_id
    WHERE v.slot_date BETWEEN ? AND ?
      AND (? = '' OR sch.shift = ?)
      AND (
        ? = ''
        OR LOWER(COALESCE(sp.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(sp.name, '')) LIKE '%' || ? || '%'
      )
      AND (
        ? = ''
        OR LOWER(COALESCE(f.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(f.name, '')) LIKE '%' || ? || '%'
      )
    GROUP BY v.slot_date, sch.shift, d.doctor_id, d.full_name, f.facility_id, f.name
    ORDER BY v.slot_date ASC, start_time ASC, d.full_name ASC
    LIMIT ?
    """

    with _connect_db() as connection:
        rows = connection.execute(
            query,
            (
                normalized_start,
                normalized_end,
                normalized_shift,
                normalized_shift,
                specialty_filter,
                specialty_filter,
                specialty.lower(),
                facility_filter,
                facility_filter,
                facility.lower(),
                limit,
            ),
        ).fetchall()

    return _json_dumps(
        [
            {
                "date": row["date"],
                "shift": row["shift"],
                "available_slots": int(row["available_slots"] or 0),
                "doctor_id": int(row["doctor_id"]),
                "doctor_name": row["doctor_name"],
                "facility_id": int(row["facility_id"]),
                "facility_name": row["facility_name"],
                "start_time": _to_hhmm(row["start_time"]),
                "end_time": _to_hhmm(row["end_time"]),
            }
            for row in rows
        ]
    )


@tool
def get_next_available_slot(
    specialty: str = "",
    facility: str = "",
    shift: str = "",
) -> str:
    """Return the earliest available slot matching the filters."""
    normalized_shift = _normalize_shift(shift)
    specialty_filter = _normalize_text(specialty)
    facility_filter = _normalize_text(facility)

    query = """
    SELECT
        v.slot_date,
        sch.shift,
        time(v.start_at) AS start_time,
        d.doctor_id,
        d.full_name AS doctor_name,
        f.facility_id,
        f.name AS facility_name,
        (
            SELECT COUNT(*)
            FROM vw_available_slots v2
            JOIN doctor_schedules sch2 ON sch2.schedule_id = v2.schedule_id
            WHERE v2.doctor_id = v.doctor_id
              AND v2.slot_date = v.slot_date
              AND sch2.shift = sch.shift
              AND v2.facility_id = v.facility_id
        ) AS available_slots
    FROM vw_available_slots v
    JOIN doctor_schedules sch
      ON sch.schedule_id = v.schedule_id
    JOIN doctors d
      ON d.doctor_id = v.doctor_id
    JOIN facilities f
      ON f.facility_id = v.facility_id
    LEFT JOIN doctor_specialties ds
      ON ds.doctor_id = d.doctor_id
    LEFT JOIN specialties sp
      ON sp.specialty_id = ds.specialty_id
    WHERE v.slot_date >= ?
      AND (? = '' OR sch.shift = ?)
      AND (
        ? = ''
        OR LOWER(COALESCE(sp.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(sp.name, '')) LIKE '%' || ? || '%'
      )
      AND (
        ? = ''
        OR LOWER(COALESCE(f.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(f.name, '')) LIKE '%' || ? || '%'
      )
    ORDER BY v.slot_date ASC, v.start_at ASC, d.full_name ASC
    LIMIT 1
    """

    with _connect_db() as connection:
        row = connection.execute(
            query,
            (
                date.today().isoformat(),
                normalized_shift,
                normalized_shift,
                specialty_filter,
                specialty_filter,
                specialty.lower(),
                facility_filter,
                facility_filter,
                facility.lower(),
            ),
        ).fetchone()

    if row is None:
        return _json_dumps({"message": "Không tìm thấy slot phù hợp."})

    return _json_dumps(
        {
            "date": row["slot_date"],
            "shift": row["shift"],
            "start_time": _to_hhmm(row["start_time"]),
            "doctor_id": int(row["doctor_id"]),
            "doctor_name": row["doctor_name"],
            "facility_id": int(row["facility_id"]),
            "facility_name": row["facility_name"],
            "available_slots": int(row["available_slots"] or 0),
        }
    )


@tool
def get_doctor_by_specialty(
    specialty: str,
    facility: str = "",
    limit: int = 20,
) -> str:
    """List doctors by specialty, optionally narrowed to a facility."""
    specialty_filter = _normalize_text(specialty)
    facility_filter = _normalize_text(facility)
    limit = max(1, min(int(limit or 20), 50))

    query = """
    SELECT DISTINCT
        d.doctor_id,
        d.full_name,
        d.degrees,
        d.qualification,
        d.description,
        f.name AS facility_name,
        d.price_local
    FROM doctors d
    JOIN facilities f
      ON f.facility_id = d.facility_id
    LEFT JOIN doctor_specialties ds
      ON ds.doctor_id = d.doctor_id
    LEFT JOIN specialties sp
      ON sp.specialty_id = ds.specialty_id
    WHERE d.profile_type = 'doctor'
      AND d.is_active = 1
      AND (
        LOWER(COALESCE(sp.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(sp.name, '')) LIKE '%' || ? || '%'
      )
      AND (
        ? = ''
        OR LOWER(COALESCE(f.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(f.name, '')) LIKE '%' || ? || '%'
      )
    ORDER BY d.full_name ASC
    LIMIT ?
    """

    with _connect_db() as connection:
        rows = connection.execute(
            query,
            (
                specialty_filter,
                specialty.lower(),
                facility_filter,
                facility_filter,
                facility.lower(),
                limit,
            ),
        ).fetchall()

    return _json_dumps(
        [
            {
                "doctor_id": int(row["doctor_id"]),
                "name": row["full_name"],
                "experience": _extract_experience_label(row["description"], row["qualification"]),
                "facility": row["facility_name"],
                "degree": row["degrees"] or "",
                "price": int(row["price_local"] or 0),
            }
            for row in rows
        ]
    )


@tool
def get_available_shifts_by_date(
    date: str,
    facility: str,
    specialty: str = "",
) -> str:
    """Return the distinct available shifts for a date."""
    normalized_day = _normalize_day(date)
    specialty_filter = _normalize_text(specialty)
    facility_filter = _normalize_text(facility)

    query = """
    SELECT DISTINCT sch.shift
    FROM vw_available_slots v
    JOIN doctor_schedules sch
      ON sch.schedule_id = v.schedule_id
    JOIN facilities f
      ON f.facility_id = v.facility_id
    LEFT JOIN doctor_specialties ds
      ON ds.doctor_id = v.doctor_id
    LEFT JOIN specialties sp
      ON sp.specialty_id = ds.specialty_id
    WHERE v.slot_date = ?
      AND (
        ? = ''
        OR LOWER(COALESCE(f.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(f.name, '')) LIKE '%' || ? || '%'
      )
      AND (
        ? = ''
        OR LOWER(COALESCE(sp.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(sp.name, '')) LIKE '%' || ? || '%'
      )
    ORDER BY sch.shift
    """

    with _connect_db() as connection:
        rows = connection.execute(
            query,
            (
                normalized_day,
                facility_filter,
                facility_filter,
                facility.lower(),
                specialty_filter,
                specialty_filter,
                specialty.lower(),
            ),
        ).fetchall()

    return _json_dumps([row["shift"] for row in rows])

def _query_available_doctors(
    *,
    day: str,
    shift: str,
    specialty: str = "",
    facility: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    normalized_day = _normalize_day(day)
    normalized_shift = _normalize_shift(shift)
    specialty_filter = _normalize_text(specialty)
    facility_filter = _normalize_text(facility)
    limit = max(1, min(int(limit or 20), 50))

    query = """
    SELECT
        d.doctor_id,
        d.full_name AS doctor_name,
        COALESCE(d.degrees, '') AS degree,
        d.price_local,
        f.facility_id,
        f.name AS facility_name,
        COUNT(DISTINCT v.slot_id) AS available_slot_count,
        MIN(v.start_at) AS first_available_time,
        GROUP_CONCAT(DISTINCT sp.name) AS specialties
    FROM vw_available_slots v
    JOIN doctors d
      ON d.doctor_id = v.doctor_id
    JOIN doctor_schedules sch
      ON sch.schedule_id = v.schedule_id
    JOIN facilities f
      ON f.facility_id = v.facility_id
    LEFT JOIN doctor_specialties ds
      ON ds.doctor_id = d.doctor_id
    LEFT JOIN specialties sp
      ON sp.specialty_id = ds.specialty_id
    WHERE v.slot_date = ?
      AND (? = '' OR sch.shift = ?)
      AND d.profile_type = 'doctor'
      AND d.is_active = 1
      AND sch.status = 'active'
      AND (
        ? = ''
        OR LOWER(COALESCE(sp.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(sp.name, '')) LIKE '%' || ? || '%'
      )
      AND (
        ? = ''
        OR LOWER(COALESCE(f.normalized_name, '')) LIKE '%' || ? || '%'
        OR LOWER(COALESCE(f.name, '')) LIKE '%' || ? || '%'
      )
    GROUP BY d.doctor_id, d.full_name, d.degrees, d.price_local, f.facility_id, f.name
    ORDER BY available_slot_count DESC, first_available_time ASC, d.full_name ASC
    LIMIT ?
    """

    with _connect_db() as connection:
        rows = connection.execute(
            query,
            (
                normalized_day,
                normalized_shift,
                normalized_shift,
                specialty_filter,
                specialty_filter,
                specialty.lower(),
                facility_filter,
                facility_filter,
                facility.lower(),
                limit,
            ),
        ).fetchall()

    return [
        {
            "id": int(row["doctor_id"]),
            "name": row["doctor_name"],
            "degree": row["degree"],
            "price": int(row["price_local"] or 0),
            "facility_id": int(row["facility_id"]),
            "facility_name": row["facility_name"],
            "available_slot_count": int(row["available_slot_count"] or 0),
            "first_available_time": row["first_available_time"] or "",
            "specialties": row["specialties"] or "",
        }
        for row in rows
    ]


@tool
def get_suitable_availability_doctor(
    day: str,
    shift: str,
    specialty: str = "",
    facility: str = "",
    symptom_text: str = "",
    limit: int = 20,
) -> str:
    """Return available doctors for the selected day, shift, specialty, and facility."""
    inferred_specialty = specialty or _infer_specialty(symptom_text)
    items = _query_available_doctors(
        day=day,
        shift=shift,
        specialty=inferred_specialty,
        facility=facility,
        limit=limit,
    )
    return _json_dumps(
        {
            "query": {
                "day": _normalize_day(day),
                "shift": _normalize_shift(shift),
                "specialty": inferred_specialty,
                "facility": facility,
            },
            "total": len(items),
            "items": items,
        }
    )


@tool
def get_suitable_availibility_doctor(
    day: str,
    shift: str,
    specialty: str = "",
    facility: str = "",
    symptom_text: str = "",
    limit: int = 20,
) -> str:
    """Backward-compatible alias of get_suitable_availability_doctor."""
    return get_suitable_availability_doctor.invoke(
        {
            "day": day,
            "shift": shift,
            "specialty": specialty,
            "facility": facility,
            "symptom_text": symptom_text,
            "limit": limit,
        }
    )


@tool
def check_availability(
    doctor_id: int,
    day: str = "",
    shift: str = "",
    facility_id: int | None = None,
    limit: int = 20,
) -> str:
    """Return appointment slots for a selected doctor."""
    normalized_day = _normalize_day(day) if day else ""
    normalized_shift = _normalize_shift(shift)
    limit = max(1, min(int(limit or 20), 50))
    facility_filter = int(facility_id) if facility_id else None

    query = """
    SELECT
        v.slot_id,
        v.slot_date,
        v.start_at,
        v.end_at,
        v.facility_id,
        f.name AS facility_name,
        d.full_name AS doctor_name
    FROM vw_available_slots v
    JOIN doctor_schedules sch
      ON sch.schedule_id = v.schedule_id
    JOIN facilities f
      ON f.facility_id = v.facility_id
    JOIN doctors d
      ON d.doctor_id = v.doctor_id
    WHERE v.doctor_id = ?
      AND (? = '' OR v.slot_date = ?)
      AND (? = '' OR sch.shift = ?)
      AND (? IS NULL OR v.facility_id = ?)
    ORDER BY v.start_at ASC
    LIMIT ?
    """

    with _connect_db() as connection:
        rows = connection.execute(
            query,
            (
                int(doctor_id),
                normalized_day,
                normalized_day,
                normalized_shift,
                normalized_shift,
                facility_filter,
                facility_filter,
                limit,
            ),
        ).fetchall()

    items = [
        {
            "id": int(row["slot_id"]),
            "time": _format_slot_time(row["start_at"], row["slot_date"]),
            "facility_id": int(row["facility_id"]),
            "facility_name": row["facility_name"],
            "doctor_name": row["doctor_name"],
            "start_at": row["start_at"],
            "end_at": row["end_at"],
        }
        for row in rows
    ]
    return _json_dumps(
        {
            "query": {
                "doctor_id": int(doctor_id),
                "day": normalized_day,
                "shift": normalized_shift,
                "facility_id": facility_filter,
            },
            "total": len(items),
            "items": items,
        }
    )


@tool
def get_today_date() -> str:
    """Return today's date in YYYY-MM-DD format."""
    return date.today().isoformat()


@tool
def calculate_age(birth_date: str) -> str:
    """Calculate age from birth date in YYYY-MM-DD format."""
    try:
        birth = datetime.strptime(birth_date, "%Y-%m-%d")
    except ValueError:
        return "Birth date format should be YYYY-MM-DD."

    today = date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return str(age)


@tool
def get_all_specialties(facility: str) -> str:
    """Return specialties available in a facility."""
    facility_filter = _normalize_text(facility)
    with _connect_db() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT sp.name
            FROM specialties sp
            JOIN doctor_specialties ds ON ds.specialty_id = sp.specialty_id
            JOIN doctors d ON d.doctor_id = ds.doctor_id
            JOIN doctor_schedules sch ON sch.doctor_id = d.doctor_id
            JOIN facilities f ON f.facility_id = sch.facility_id
            WHERE (
                ? = ''
                OR LOWER(COALESCE(f.normalized_name, '')) LIKE '%' || ? || '%'
                OR LOWER(COALESCE(f.name, '')) LIKE '%' || ? || '%'
            )
              AND d.is_active = 1
              AND sch.status = 'active'
            ORDER BY sp.name
            """,
            (facility_filter, facility_filter, facility.lower()),
        ).fetchall()

    if not rows:
        return f"Khong tim thay chuyen khoa nao trong co so '{facility}'."
    return "\n".join(row["name"] for row in rows)


@tool
def get_doctor_schedule(doctor_name: str) -> str:
    """Return the doctor's future schedules and remaining slots."""
    normalized_name = _normalize_text(doctor_name)
    with _connect_db() as connection:
        doctors = connection.execute(
            """
            SELECT DISTINCT doctor_id, full_name
            FROM doctors
            WHERE profile_type = 'doctor'
              AND (
                    normalized_name LIKE '%' || ? || '%'
                 OR LOWER(full_name) LIKE '%' || ? || '%'
              )
            ORDER BY full_name
            LIMIT 5
            """,
            (normalized_name, doctor_name.lower()),
        ).fetchall()

        if not doctors:
            return f"Không tìm thấy bác sĩ nào có tên '{doctor_name}'."

        output: list[str] = []
        for doctor in doctors:
            output.append(f"📅 Lịch làm việc của bác sĩ {doctor['full_name']}:")
            schedules = connection.execute(
                """
                SELECT
                    ds.work_date,
                    ds.shift,
                    ds.start_at,
                    ds.end_at,
                    SUM(CASE WHEN slot.status = 'available' THEN 1 ELSE 0 END) AS available_slots,
                    COUNT(slot.slot_id) AS total_slots
                FROM doctor_schedules ds
                LEFT JOIN doctor_schedule_slots slot ON slot.schedule_id = ds.schedule_id
                WHERE ds.doctor_id = ?
                GROUP BY ds.schedule_id
                ORDER BY ds.work_date, ds.start_at
                LIMIT 12
                """,
                (int(doctor["doctor_id"]),),
            ).fetchall()

            if not schedules:
                output.append("  Không có lịch làm việc.")
                continue

            for row in schedules:
                available = int(row["available_slots"] or 0)
                total = int(row["total_slots"] or 0)
                output.append(
                    f"  - Ngày: {row['work_date']} | Ca: {row['shift']} | Giờ: {row['start_at']} - {row['end_at']} "
                    f"| Còn trống: {available}/{total}"
                )
            output.append("")

    return "\n".join(output).strip()


@tool
def get_doctor_profile(doctor_name: str) -> dict[str, Any]:
    """Return a doctor's profile and a few next available slots."""
    normalized_name = _normalize_text(doctor_name)
    with _connect_db() as connection:
        row = connection.execute(
            """
            SELECT
                d.doctor_id,
                d.full_name,
                d.degrees,
                d.description,
                d.qualification,
                d.raw_speciality,
                d.price_local,
                d.price_foreigner,
                f.name AS facility_name
            FROM doctors d
            JOIN facilities f ON f.facility_id = d.facility_id
            WHERE d.profile_type = 'doctor'
              AND (
                    d.normalized_name LIKE '%' || ? || '%'
                 OR LOWER(d.full_name) LIKE '%' || ? || '%'
              )
            ORDER BY d.full_name
            LIMIT 1
            """,
            (normalized_name, doctor_name.lower()),
        ).fetchone()

        if row is None:
            return {"error": f"Không tìm thấy bác sĩ '{doctor_name}' trong hệ thống."}

        slots = connection.execute(
            """
            SELECT slot_id, slot_date, start_at
            FROM vw_available_slots
            WHERE doctor_id = ?
            ORDER BY start_at
            LIMIT 3
            """,
            (int(row["doctor_id"]),),
        ).fetchall()

    profile = {
        "doctor_id": int(row["doctor_id"]),
        "name": row["full_name"],
        "degrees": row["degrees"] or "",
        "description": row["description"] or "",
        "speciality": row["raw_speciality"] or "",
        "qualification": row["qualification"] or "",
        "vinmec_site": row["facility_name"] or "",
        "price_local": int(row["price_local"] or 0),
        "price_foreigner": int(row["price_foreigner"] or 0),
        "next_slots": [
            {"slot_id": int(slot["slot_id"]), "time": _format_slot_time(slot["start_at"], slot["slot_date"])}
            for slot in slots
        ],
    }
    return {"profile": profile}


@tool
def estimate_cost(doctor_id: int, nationality: str = "local") -> str:
    """Estimate the consultation cost for a doctor."""
    with _connect_db() as connection:
        row = connection.execute(
            """
            SELECT doctor_id, full_name, price_local, price_foreigner
            FROM doctors
            WHERE doctor_id = ?
            LIMIT 1
            """,
            (int(doctor_id),),
        ).fetchone()

    if row is None:
        return _json_dumps({"message": "Không tìm thấy bác sĩ.", "price": 0, "currency": "VND"})

    nationality_key = _normalize_text(nationality)
    price = int(row["price_foreigner"] or 0) if nationality_key == "foreign" else int(row["price_local"] or 0)
    return _json_dumps(
        {
            "doctor_id": int(row["doctor_id"]),
            "doctor_name": row["full_name"],
            "price": price,
            "currency": "VND",
        }
    )


@tool
def get_doctor_rating(doctor_id: int) -> str:
    """Return a doctor rating. Uses a stable mock because the current DB has no review table."""
    return _json_dumps(_mock_rating_for_doctor(int(doctor_id)))


@tool
def suggest_best_option(
    specialty: str,
    facility: str = "",
    priority: str = "earliest",
) -> str:
    """Suggest the best appointment option by earliest slot or best rated doctor."""
    priority_key = _normalize_text(priority)

    if priority_key == "earliest":
        result = json.loads(
            get_next_available_slot.invoke(
                {
                    "specialty": specialty,
                    "facility": facility,
                }
            )
        )
        if result.get("doctor_name"):
            result["reason"] = "earliest available"
        return _json_dumps(result)

    start_date = date.today().isoformat()
    end_date = _future_end_date(30)
    rows = json.loads(
        search_doctor_availability_range.invoke(
            {
                "start_date": start_date,
                "end_date": end_date,
                "specialty": specialty,
                "facility": facility,
                "limit": 200,
            }
        )
    )
    if not rows:
        return _json_dumps({"message": "Không tìm thấy lựa chọn phù hợp."})

    best_row = max(
        rows,
        key=lambda item: (
            _mock_rating_for_doctor(int(item["doctor_id"]))["rating"],
            item["available_slots"],
            item["date"],
            item["start_time"],
        ),
    )
    rating_payload = _mock_rating_for_doctor(int(best_row["doctor_id"]))
    return _json_dumps(
        {
            "doctor_id": int(best_row["doctor_id"]),
            "doctor_name": best_row["doctor_name"],
            "date": best_row["date"],
            "shift": best_row["shift"],
            "start_time": best_row["start_time"],
            "end_time": best_row["end_time"],
            "available_slots": int(best_row["available_slots"]),
            "facility": best_row["facility_name"],
            "rating": rating_payload["rating"],
            "review_count": rating_payload["review_count"],
            "reason": "best rated doctor with availability",
        }
    )


@tool
def summarize_consultation(
    phone: str,
    full_name: str = "",
    gender: str = "",
    email: str = "",
    date_of_birth: str = "",
    symptom_summary: str = "",
    specialty: str = "",
    facility: str = "",
    facility_id: int | None = None,
    doctor: str = "",
    doctor_id: int | None = None,
    appointment_time: str = "",
    slot_id: int | None = None,
    note: str = "",
) -> str:
    """Return the final confirmation payload inside a UI_CONFIRM tag."""
    payload = {
        "patient": {
            "full_name": full_name,
            "gender": gender,
            "email": email,
            "phone": _digits_only(phone),
            "date_of_birth": date_of_birth,
        },
        "consultation": {
            "symptom_summary": symptom_summary,
            "specialty": specialty,
            "facility": facility,
            "facility_id": facility_id,
            "doctor": doctor,
            "doctor_id": doctor_id,
            "appointment_time": appointment_time,
            "slot_id": slot_id,
            "note": note,
        },
        "status": "pending_confirmation",
    }
    return f"<UI_CONFIRM>{_json_dumps(payload)}</UI_CONFIRM>"


@tool
def confirm_appointment_summary(
    full_name: str,
    phone: str,
    specialty: str,
    facility: str,
    preferred_time: str,
    note: str = "",
) -> str:
    """Backward-compatible alias returning UI_CONFIRM."""
    return summarize_consultation.invoke(
        {
            "phone": phone,
            "full_name": full_name,
            "symptom_summary": note,
            "specialty": specialty,
            "facility": facility,
            "appointment_time": preferred_time,
            "note": note,
        }
    )


def _upsert_user(
    connection: sqlite3.Connection,
    *,
    phone: str,
    full_name: str,
    email: str = "",
    date_of_birth: str = "",
    gender: str = "",
    nationality_type: str = "local",
) -> int:
    normalized_phone = _digits_only(phone)
    existing = connection.execute(
        "SELECT user_id FROM users WHERE phone = ? LIMIT 1",
        (normalized_phone,),
    ).fetchone()

    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO users (full_name, normalized_name, phone, email, date_of_birth, gender, nationality_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                _normalize_text(full_name),
                normalized_phone,
                email,
                date_of_birth,
                gender,
                nationality_type,
            ),
        )
        return int(cursor.lastrowid)

    connection.execute(
        """
        UPDATE users
        SET
            full_name = COALESCE(NULLIF(?, ''), full_name),
            normalized_name = CASE WHEN ? <> '' THEN ? ELSE normalized_name END,
            email = COALESCE(NULLIF(?, ''), email),
            date_of_birth = COALESCE(NULLIF(?, ''), date_of_birth),
            gender = COALESCE(NULLIF(?, ''), gender),
            nationality_type = COALESCE(NULLIF(?, ''), nationality_type),
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (
            full_name,
            full_name,
            _normalize_text(full_name),
            email,
            date_of_birth,
            gender,
            nationality_type,
            int(existing["user_id"]),
        ),
    )
    return int(existing["user_id"])


@tool
def create_consultation(
    slot_id: int,
    full_name: str,
    phone: str,
    specialty: str = "",
    symptom_text: str = "",
    nationality_type: str = "local",
    email: str = "",
    date_of_birth: str = "",
    gender: str = "",
    booking_note: str = "",
) -> str:
    """Persist an appointment after user confirmation."""
    normalized_phone = _digits_only(phone)
    normalized_name = (full_name or "").strip()
    if not normalized_name:
        return _json_dumps({"status": "error", "message": "Thiếu họ tên bệnh nhân."})
    if len(normalized_phone) < 9:
        return _json_dumps({"status": "error", "message": "Số điện thoại không hợp lệ."})

    with _connect_db() as connection:
        try:
            connection.execute("BEGIN")

            slot = connection.execute(
                """
                SELECT
                    v.slot_id,
                    v.schedule_id,
                    v.doctor_id,
                    v.facility_id,
                    v.slot_date,
                    v.start_at,
                    v.end_at,
                    d.full_name AS doctor_name,
                    f.name AS facility_name,
                    d.price_local,
                    d.price_foreigner
                FROM vw_available_slots v
                JOIN doctors d ON d.doctor_id = v.doctor_id
                JOIN facilities f ON f.facility_id = v.facility_id
                WHERE v.slot_id = ?
                LIMIT 1
                """,
                (int(slot_id),),
            ).fetchone()

            if slot is None:
                connection.rollback()
                return _json_dumps(
                    {
                        "status": "error",
                        "message": "Khung giờ này không còn khả dụng. Vui lòng chọn giờ khám khác.",
                    }
                )

            specialty_id, resolved_specialty = _resolve_specialty_id(connection, specialty)
            user_id = _upsert_user(
                connection,
                phone=normalized_phone,
                full_name=normalized_name,
                email=email,
                date_of_birth=date_of_birth,
                gender=gender,
                nationality_type=nationality_type,
            )

            fee = int(slot["price_local"] or 0)
            if nationality_type == "foreigner":
                fee = int(slot["price_foreigner"] or 0)

            cursor = connection.execute(
                """
                INSERT INTO appointments (
                    user_id, doctor_id, facility_id, specialty_id, slot_id,
                    symptom_text, booking_note, nationality_type, consultation_fee,
                    status, confirmed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', CURRENT_TIMESTAMP)
                """,
                (
                    user_id,
                    int(slot["doctor_id"]),
                    int(slot["facility_id"]),
                    specialty_id,
                    int(slot["slot_id"]),
                    symptom_text,
                    booking_note,
                    nationality_type,
                    fee,
                ),
            )
            appointment_id = int(cursor.lastrowid)

            connection.execute(
                "UPDATE doctor_schedule_slots SET status = 'booked' WHERE slot_id = ?",
                (int(slot["slot_id"]),),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
            return _json_dumps(
                {
                    "status": "error",
                    "message": "Khung giờ này vừa được đặt. Vui lòng chọn khung giờ khác.",
                }
            )
        except sqlite3.Error as exc:
            connection.rollback()
            return _json_dumps({"status": "error", "message": f"Lỗi khi tạo lịch hẹn: {exc}"})

    return _json_dumps(
        {
            "status": "success",
            "appointment_id": appointment_id,
            "patient_name": normalized_name,
            "phone": normalized_phone,
            "doctor": slot["doctor_name"],
            "facility": slot["facility_name"],
            "specialty": resolved_specialty or specialty,
            "time": _format_slot_window(slot["start_at"], slot["end_at"]),
            "fee": fee,
            "slot_id": int(slot["slot_id"]),
        }
    )


@tool
def book_appointment(
    full_name: str,
    phone: str,
    specialty: str,
    facility: str,
    preferred_date: str,
    shift: str,
    symptom_text: str = "",
    nationality_type: str = "local",
) -> str:
    """Backward-compatible booking tool that finds the first slot and confirms it."""
    doctors_payload = json.loads(
        get_suitable_availability_doctor.invoke(
            {
                "day": preferred_date,
                "shift": shift,
                "specialty": specialty,
                "facility": facility,
                "symptom_text": symptom_text,
                "limit": 1,
            }
        )
    )
    doctor_items = doctors_payload.get("items", [])
    if not doctor_items:
        return (
            f"❌ Không còn slot trống vào ngày {_normalize_day(preferred_date)} "
            f"ca {_normalize_shift(shift)} tại {facility}.\n"
            "Vui lòng chọn ngày hoặc ca khác."
        )

    slots_payload = json.loads(
        check_availability.invoke(
            {
                "doctor_id": int(doctor_items[0]["id"]),
                "day": preferred_date,
                "shift": shift,
                "facility_id": int(doctor_items[0]["facility_id"]),
                "limit": 1,
            }
        )
    )
    slot_items = slots_payload.get("items", [])
    if not slot_items:
        return (
            f"❌ Không còn slot trống vào ngày {_normalize_day(preferred_date)} "
            f"ca {_normalize_shift(shift)} tại {facility}.\n"
            "Vui lòng chọn ngày hoặc ca khác."
        )

    booking_result = json.loads(
        create_consultation.invoke(
            {
                "slot_id": int(slot_items[0]["id"]),
                "full_name": full_name,
                "phone": phone,
                "specialty": specialty,
                "symptom_text": symptom_text,
                "nationality_type": nationality_type,
            }
        )
    )
    if booking_result.get("status") != "success":
        return f"❌ {booking_result.get('message', 'Không thể đặt lịch.')}"

    return (
        f"✅ Đặt lịch thành công! Mã lịch hẹn: #{booking_result['appointment_id']}\n\n"
        "📋 Thông tin xác nhận:\n"
        f"- Họ tên:          {booking_result['patient_name']}\n"
        f"- Số điện thoại:   {booking_result['phone']}\n"
        f"- Bác sĩ:          {booking_result['doctor']}\n"
        f"- Chuyên khoa:     {booking_result.get('specialty') or specialty}\n"
        f"- Cơ sở Vinmec:    {booking_result['facility']}\n"
        f"- Thời gian khám:  {booking_result['time']}\n"
        f"- Chi phí:         {booking_result['fee']:,} VNĐ\n"
        f"- Triệu chứng:     {symptom_text or 'Không có'}\n\n"
        "📌 Vui lòng đến trước giờ hẹn 15 phút và mang theo CMND/CCCD."
    )


tools_list = [
    identify_user,
    get_user_profile,
    triage_symptom_checker,
    recommend_specialty_from_symptom,
    get_hospital_locations,
    search_doctor_availability_range,
    get_next_available_slot,
    get_doctor_by_specialty,
    get_available_shifts_by_date,
    get_suitable_availability_doctor,
    check_availability,
    estimate_cost,
    get_doctor_rating,
    suggest_best_option,
    summarize_consultation,
    create_consultation,
    get_today_date,
    get_nearest_branch,
    get_all_specialties,
    get_doctor_profile,
    get_doctor_schedule,
    get_suitable_availibility_doctor,
    confirm_appointment_summary,
    book_appointment,
]
