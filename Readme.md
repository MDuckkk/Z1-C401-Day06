## Vinmec Local

Chatbot này chạy local với:

- `LangGraph` để giữ flow `agent -> tools -> agent`
- `SQLite` làm nguồn dữ liệu cơ sở, bác sĩ, lịch khám
- `Streamlit` làm frontend chat, render XML UI tags thành card tương tác

### Các điểm chính

- Giữ nguyên kiến trúc agent hiện có, không đổi graph flow trong `agent.py`
- Thêm workflow y tế mới:
  - `identify_user`
  - `triage_symptom_checker`
  - `get_hospital_locations`
  - `get_suitable_availability_doctor`
  - `check_availability`
  - `summarize_consultation`
  - `create_consultation`
- Frontend không hiển thị danh sách bằng text thường
- Dữ liệu cơ sở, bác sĩ, giờ khám được render từ UI tags
- Có pagination 3 item/lần và nút `Xem thêm`

### Cấu trúc file quan trọng

- `agent.py`: LangGraph agent
- `tools.py`: toàn bộ tool backend và compatibility wrappers
- `system_prompt.txt`: persona + workflow + UI rules
- `chat_backend.py`: lớp trung gian giữa agent và frontend
- `app.py`: local web UI bằng Streamlit

### Yêu cầu môi trường

- Python 3.10+
- Một trong các token sau:
  - `OPENAI_API_KEY`
  - `GITHUB_TOKEN`
  - `GITHUB_ACCESS_TOKEN`

### Cài đặt

```bash
cd assignments/Z1-C401-Day06
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Biến môi trường

Tạo file `.env`:

```env
OPENAI_API_KEY=your_openai_api_key
```

Hoặc dùng GitHub Models:

```env
GITHUB_TOKEN=your_github_pat_with_models_scope
GITHUB_MODEL=openai/gpt-4o-mini
```

Tùy chọn:

```env
VINMEC_DB_PATH=/absolute/path/to/vinmec.sqlite
OPENAI_BASE_URL=https://your-openai-compatible-endpoint
GITHUB_MODELS_BASE_URL=https://models.github.ai/inference
```

Nếu không khai báo `VINMEC_DB_PATH`, hệ thống sẽ dùng mặc định `data/vinmec.sqlite`.

### Chạy local UI

```bash
cd assignments/Z1-C401-Day06
streamlit run app.py
```

Sau khi chạy, mở URL local do Streamlit in ra, thường là:

```text
http://localhost:8501
```

### Cách dùng nhanh

1. Nhập số điện thoại để xác thực.
2. Mô tả triệu chứng.
3. Chọn cơ sở bằng card.
4. Chọn bác sĩ bằng card.
5. Chọn giờ khám bằng card.
6. Xác nhận thông tin.
7. Hệ thống tạo lịch và hiển thị trạng thái thành công.

### Lưu ý

- `Xem thêm` được xử lý ở frontend bằng cache full-result từ tool output.
- `summarize_consultation` trả về thẻ `<UI_CONFIRM>` nguyên khối.
- Sau khi tạo lịch thành công, frontend hiển thị trạng thái `UI_RATING`.
