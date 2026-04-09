# Báo cáo thiết kế SQLite — Agent đặt lịch khám

## Cách chạy

### 1. Tạo database

```bash
python scripts/create_db.py
```

Mặc định tạo DB tại `data/vinmec.sqlite`.

### 2. Import dữ liệu

```bash
python scripts/import_data.py
```

Tùy chọn đổi độ dài slot (mặc định 30 phút):

```bash
python scripts/import_data.py --slot-minutes 20
```

Các tham số khác:

| Tham số | Mặc định |
|---|---|
| `--db` | `data/vinmec.sqlite` |
| `--doctors` | `danh_sach_bac_si.csv` |
| `--facilities` | `danh_sach_co_so.csv` |
| `--specialties` | `chuyen_khoa.csv` |
| `--schedules` | `doctor_schedule.csv` |

### Kết quả import đã kiểm chứng

| Bảng | Số bản ghi |
|---|---|
| `facilities` | 11 |
| `specialties` | 73 |
| `doctors` | 524 |
| `doctor_specialties` | 447 |
| `doctor_schedules` | 4348 |
| `doctor_schedule_slots` | 34784 |
| `users` | 0 |
| `appointments` | 0 |

> `doctor_schedule.csv` có 4351 dòng, sau import còn 4348 do 3 dòng trùng unique key.

---

## Cấu trúc database

### `users`

Thông tin người dùng phục vụ đặt lịch.

| Cột | Ghi chú |
|---|---|
| `full_name`, `normalized_name` | Tên gốc và tên đã chuẩn hóa |
| `phone`, `email` | Có index |
| `date_of_birth`, `gender` | |
| `nationality_type` | `local` hoặc `foreigner` |
| `identity_no`, `address` | |

### `facilities`

Cơ sở khám chữa bệnh.

| Cột | Ghi chú |
|---|---|
| `name` | Tên gốc, unique |
| `normalized_name` | Tên đã chuẩn hóa, dùng để lookup |
| `address`, `province` | Province tách từ địa chỉ |
| `latitude`, `longitude` | Hiện để NULL, dự phòng tính khoảng cách |

### `specialties`

Danh mục chuyên khoa.

| Cột | Ghi chú |
|---|---|
| `source_specialty_id` | ID gốc từ `chuyen_khoa.csv` |
| `name`, `normalized_name` | |
| `is_master` | `1` = từ danh mục gốc, `0` = tạo thêm khi không map được |

### `doctors`

Hồ sơ bác sĩ.

| Cột | Ghi chú |
|---|---|
| `full_name`, `normalized_name` | |
| `degrees`, `description`, `qualification` | Thông tin hồ sơ |
| `raw_speciality` | Chuỗi chuyên khoa gốc từ CSV |
| `facility_id` | FK → `facilities` |
| `price_local`, `price_foreigner` | Giá khám theo loại bệnh nhân |
| `profile_type` | `doctor` / `service` / `unknown` |

Unique key: `(normalized_name, facility_id)`.

### `doctor_specialties`

Bảng nối `doctors` ↔ `specialties`.

### `doctor_schedules`

Mỗi dòng là một ca làm việc của bác sĩ.

| Cột | Ghi chú |
|---|---|
| `doctor_id`, `facility_id` | |
| `work_date` | Ngày làm việc |
| `shift` | `morning` / `afternoon` / `evening` / `full_day` / `custom` |
| `start_at`, `end_at` | Giờ bắt đầu/kết thúc ca |
| `status` | `active` / `cancelled` |

Unique key: `(doctor_id, work_date, shift, start_at, end_at)`.

### `doctor_schedule_slots`

Slot nhỏ sinh ra từ `doctor_schedules` (mặc định 30 phút/slot).

| Cột | Ghi chú |
|---|---|
| `schedule_id`, `doctor_id` | |
| `slot_date`, `start_at`, `end_at` | |
| `status` | `available` / `booked` / `blocked` / `completed` / `cancelled` |

Unique key: `(doctor_id, start_at, end_at)`.

### `appointments`

Lịch hẹn đã đặt.

| Cột | Ghi chú |
|---|---|
| `user_id`, `doctor_id`, `facility_id`, `specialty_id` | |
| `slot_id` | FK → `doctor_schedule_slots`, unique |
| `symptom_text`, `booking_note` | |
| `nationality_type` | Xác định giá khám |
| `consultation_fee` | Phí tại thời điểm đặt |
| `status` | `pending` / `confirmed` / `completed` / `cancelled` / `no_show` |

### View `vw_available_slots`

Trả về slot còn trống: `status = 'available'` và chưa có appointment `pending/confirmed`.

---

## Chuẩn hóa dữ liệu

### Nguyên tắc chung

Dữ liệu gốc được giữ nguyên trong các cột `full_name`, `raw_speciality`, v.v. Cột `normalized_name` chỉ dùng cho lookup và dedup, không thay thế dữ liệu gốc.

### 1. Chuẩn hóa text (`normalize_text`)

Áp dụng cho tên bác sĩ, cơ sở, chuyên khoa trước khi lưu vào `normalized_name`:

1. Strip BOM (`\ufeff`), lowercase
2. Chuyển `đ/Đ` → `d/D` thủ công (trước bước NFKD để tránh mất ký tự)
3. `unicodedata.normalize("NFKD")` + bỏ combining characters → loại toàn bộ dấu
4. Xóa ký tự không phải `a-z0-9`, collapse whitespace

Ví dụ: `"Bệnh viện Đa khoa Quốc tế"` → `"benh vien da khoa quoc te"`

### 2. Matching cơ sở (`facility_lookup_key`)

Cùng một cơ sở có thể xuất hiện với nhiều cách viết khác nhau giữa các file CSV:

- Expand viết tắt: `dkqt` → `da khoa quoc te`
- Strip prefix chuẩn (ví dụ `benh vien da khoa quoc te vinmec `) để lấy phần định danh
- Nếu cơ sở chỉ xuất hiện trong file bác sĩ mà không có trong `danh_sach_co_so.csv`, script tự tạo bản ghi mới

### 3. Mapping chuyên khoa

Chuyên khoa trong CSV bác sĩ là free-text, không khớp exact với danh mục:

1. Normalize text
2. Tra bảng alias cứng (`SPECIALTY_ALIAS_TO_MASTER`, ~12 entry) để map về specialty master
3. Nếu không map được → tạo specialty mở rộng với `is_master=0` thay vì bỏ dữ liệu

Một số alias ví dụ:

| Giá trị trong CSV | Map về |
|---|---|
| `phu khoa`, `khoa san`, `san khoa` | `san phu khoa` |
| `tieu hoa`, `noi tieu hoa noi soi` | `noi tieu hoa` |
| `vaccine` | `tiem chung vac xin` |
| `ung buou xa tri` | `trung tam ung buou` |

### 4. Dedup bác sĩ trùng tên

`doctor_schedule.csv` chỉ có tên bác sĩ, không có `facility_id`. Khi một tên xuất hiện ở nhiều cơ sở, script chọn bản ghi có `completeness_score` cao nhất:

```
score = len(degrees) + len(speciality) + len(description) + len(qualification)
```

Có 4 trường hợp trùng tên đã được resolve theo rule này.

### 5. Sinh slot từ ca làm việc

Mỗi `doctor_schedules` được tách thành các slot nhỏ liên tiếp (mặc định 30 phút) lưu vào `doctor_schedule_slots`. Slot cuối bị bỏ nếu không đủ độ dài.
