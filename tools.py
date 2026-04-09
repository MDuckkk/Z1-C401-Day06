import sqlite3
from datetime import date
from pathlib import Path
from langchain_core.tools import tool

_DB_PATH = Path(__file__).resolve().parent / "data" / "vinmec.sqlite"
_TODAY = date.today().isoformat()  # "2026-04-09" — dạng TEXT khớp với DB


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@tool
def get_doctor_profile(doctor_name: str) -> dict:
    """
    Tìm và trả về thông tin của bác sĩ, bao gồm profile đầy đủ và lịch làm việc sắp tới.

    Args:
        doctor_name: Tên đầy đủ của bác sĩ (chính xác theo danh sách)

    Returns:
        Profile đầy đủ và lịch làm việc của bác sĩ.
    """
    with _get_connection() as conn:
        # --- Profile ---
        row = conn.execute(
            """
            SELECT d.doctor_id, d.full_name, d.degrees, d.description,
                   d.qualification, d.raw_speciality,
                   d.price_local, d.price_foreigner,
                   f.name AS facility_name
            FROM doctors d
            JOIN facilities f ON f.facility_id = d.facility_id
            WHERE d.full_name = ?
              AND d.profile_type = 'doctor'
            LIMIT 1
            """,
            (doctor_name,),
        ).fetchone()

        if row is None:
            return {"error": f"Không tìm thấy bác sĩ '{doctor_name}' trong hệ thống."}

        profile = {
            "name":            row["full_name"],
            "degrees":         row["degrees"] or "",
            "description":     row["description"] or "",
            "speciality":      row["raw_speciality"] or "",
            "qualification":   row["qualification"] or "",
            "vinmec_site":     row["facility_name"] or "",
            "price_local":     row["price_local"],
            "price_foreigner": row["price_foreigner"],
        }


    return {"profile": profile}
