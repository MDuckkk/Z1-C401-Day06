"""
Script kiểm nghiệm tool get_doctor_profile.
Chạy: python test_tool.py
"""
import sqlite3
import json
from pathlib import Path
from tools import get_doctor_profile

DB_PATH = Path(__file__).resolve().parent / "data" / "vinmec.sqlite"

# --- Lấy tên bác sĩ thực từ DB ---
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT full_name FROM doctors WHERE profile_type = 'doctor' LIMIT 1"
).fetchone()
conn.close()

doctor_name = row["full_name"] if row else None

print("=" * 60)
print("TEST 1: Bác sĩ hợp lệ")
print("=" * 60)
if doctor_name:
    print(f"Tên bác sĩ: {doctor_name}")
    result = get_doctor_profile.invoke({"doctor_name": doctor_name})
    print(json.dumps(result, ensure_ascii=False, indent=2))
else:
    print("Không tìm thấy bác sĩ nào trong DB.")

print()
print("=" * 60)
print("TEST 2: Bác sĩ KHÔNG tồn tại")
print("=" * 60)
result2 = get_doctor_profile.invoke({"doctor_name": "Bác sĩ Giả Mạo XYZ"})
print(json.dumps(result2, ensure_ascii=False, indent=2))
