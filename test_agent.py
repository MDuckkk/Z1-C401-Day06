from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from agent import graph, has_llm_credentials


ROOT_DIR = Path(__file__).resolve().parent
DB_CANDIDATES = [
    ROOT_DIR / "data" / "vinmec.sqlite",
    ROOT_DIR / "vinmec.sqlite3",
]


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


configure_stdout()


def resolve_db_path() -> Path:
    for candidate in DB_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Khong tim thay file database de tao test cases.")


def get_sample_context() -> dict[str, str]:
    db_path = resolve_db_path()
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        facility_row = cursor.execute(
            "SELECT name FROM facilities WHERE name IS NOT NULL ORDER BY facility_id LIMIT 1"
        ).fetchone()
        specialty_row = cursor.execute(
            "SELECT name FROM specialties WHERE name IS NOT NULL ORDER BY specialty_id LIMIT 1"
        ).fetchone()
        doctor_row = cursor.execute(
            """
            SELECT DISTINCT d.full_name
            FROM doctors d
            WHERE d.profile_type = 'doctor' AND d.full_name IS NOT NULL
            ORDER BY d.doctor_id
            LIMIT 1
            """
        ).fetchone()
        slot_row = cursor.execute(
            """
            SELECT DISTINCT v.slot_date, sch.shift, f.name AS facility_name, d.full_name AS doctor_name
            FROM vw_available_slots v
            JOIN doctor_schedules sch ON sch.schedule_id = v.schedule_id
            JOIN facilities f ON f.facility_id = v.facility_id
            JOIN doctors d ON d.doctor_id = v.doctor_id
            ORDER BY v.slot_date, sch.shift
            LIMIT 1
            """
        ).fetchone()

    return {
        "facility": (slot_row["facility_name"] if slot_row else None) or (facility_row["name"] if facility_row else "Vinmec"),
        "specialty": (specialty_row["name"] if specialty_row else "Tim mạch"),
        "doctor": (slot_row["doctor_name"] if slot_row else None) or (doctor_row["full_name"] if doctor_row else "Bác sĩ mẫu"),
        "date": slot_row["slot_date"] if slot_row else "2026-04-09",
        "shift": slot_row["shift"] if slot_row else "morning",
    }


def build_default_questions(sample: dict[str, str]) -> list[str]:
    return [
        f"Hôm nay là ngày bao nhiêu?",
        f"Cơ sở nào gần VinUni nhất?",
        f"Có bác sĩ {sample['specialty']} nào còn lịch trống ở {sample['facility']} vào {sample['date']} ca {sample['shift']} không?",
        f"Cho tôi xem hồ sơ bác sĩ {sample['doctor']}.",
        f"{sample['facility']} có những chuyên khoa nào?",
    ]


def run_case(question: str, conversation_messages: list | None = None) -> list:
    history = conversation_messages or []
    result = graph.invoke({"messages": history + [("human", question)]})
    final = result["messages"][-1]

    print("=" * 80)
    print(f"User: {question}")
    print("-" * 80)
    print(f"Agent: {final.content}")

    return result["messages"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run smoke tests for the Vinmec agent.")
    parser.add_argument(
        "--question",
        action="append",
        dest="questions",
        help="Custom test question. Can be passed multiple times.",
    )
    parser.add_argument(
        "--keep-history",
        action="store_true",
        help="Reuse conversation history across questions.",
    )
    parser.add_argument(
        "--show-sample",
        action="store_true",
        help="Print the sampled DB context used to build default questions.",
    )
    return parser.parse_args()


def main() -> None:
    configure_stdout()
    args = parse_args()

    if not has_llm_credentials() or graph is None:
        raise EnvironmentError("Thiếu OPENAI_API_KEY hoặc GITHUB_TOKEN/GITHUB_ACCESS_TOKEN trong .env.")

    sample = get_sample_context()
    if args.show_sample:
        print(json.dumps(sample, ensure_ascii=False, indent=2))

    questions = args.questions or build_default_questions(sample)

    conversation_messages: list = []
    for question in questions:
        conversation_messages = run_case(
            question,
            conversation_messages if args.keep_history else [],
        )


if __name__ == "__main__":
    main()
