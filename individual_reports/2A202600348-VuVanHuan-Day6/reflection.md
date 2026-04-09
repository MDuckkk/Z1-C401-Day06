# Individual reflection — Nguyễn Văn A (AI20K001)

## 1. Role
- UX designer (contribute), SPEC : Evaluation + matrix

## 2. Đóng góp cụ thể
- Thiết kế conversation flow :
START
  ↓
[Chào + hỏi SĐT] → identify_user()
  ↓
[Hỏi triệu chứng] → triage_symptom_checker()
  ↓ emergency? → "Gọi 115 ngay" → END
  ↓
[Hỏi cơ sở/vị trí?] → get_hospital_locations()
  ↓
get_suitable_availability_doctor()  ← agent tự pick
  ↓
[Hiển thị bác sĩ gợi ý]
  ├─ OK → check_availability() → user chọn slot
  ├─ Muốn xem thêm → get_suitable_availability_doctor(limit=5) → compare_doctors()
  └─ Đổi tiêu chí → loop lại
  ↓
summarize_consultation() → user confirm
  ↓
create_consultation() → lưu DB
  ↓
END

## 3. SPEC mạnh/yếu
- Mạnh nhất: Xử lý Failure Modes trong Workflow — Nhóm đã lường trước được các case thực tế rủi ro cao như: "Tranh giành lịch khám" (Race Condition - user chọn đúng slot vừa bị người khác đặt) và case "Cấp cứu" (Triệu chứng nguy hiểm). Mitigation cụ thể là dùng Transaction Rollback trong DB và ngắt luồng AI ngay lập tức.

- Yếu nhất: Evaluation Metrics (Đo lường) & ROI — Ban đầu chỉ đánh giá ROI dựa trên "Số lượng lịch đặt thành công". Thiết kế này hơi ngây thơ vì bỏ qua các metric về UX như: "Tỷ lệ drop-off (bỏ ngang) khi phải đọc text quá dài" hoặc "Số lượt turn hội thoại trung bình để chốt 1 lịch". Sau đó mới phải bổ sung UI component để giảm số turn.

## 4. Đóng góp khác
- Test prompt

## 5. Điều học được
- Trước dự án, tôi nghĩ xây dựng AI Agent chỉ đơn giản là nhồi prompt và gọi hàm. Sau khi thiết kế luồng UX và Eval, tôi nhận ra: Trong các hệ thống Enterprise, AI không được phép tự do. "Hallucination" (Ảo giác) không chỉ là nói sai sự thật, mà còn là "cầm đèn chạy trước ô tô" (VD: Tự đoán user ở Hà Nội dù chưa hỏi, hoặc tự bịa ra user_id = 1 để lưu DB). Việc dùng System Prompt để trói buộc LLM, ép nó phải xuất output dạng Structured Data (JSON) để Frontend vẽ UI là bài học lớn nhất về Product Engineering.

## 6. Nếu làm lại
- Buil lại Code folder Structruc
- Sẽ thiết kế chuẩn UI Response (XML tags) ngay từ Day 1 thay vì code xong luồng Terminal rồi mới đắp Web UI lên, giúp tránh việc phải đập đi xây lại file tools.py.

## 7. AI giúp gì / AI sai gì
**Giúp**: Dùng ChatGPT để lên khung kiến trúc FastAPI, viết các câu query SQL JOIN phức tạp.

**Sai/mislead**: Khi được yêu cầu làm Chatbot, AI luôn có xu hướng mặc định khuyên dùng thiết kế "Text-based" (bắt user gõ phím để chọn 1, 2, 3). Nếu nghe theo AI, UX của sản phẩm sẽ rất tệ. Tôi đã phải kiên quyết "ép" AI phải làm theo luồng sinh JSON để Frontend vẽ Button.

**Bài học**: AI (LLM trong Agent) rất lanh chanh, thường tự ý bỏ qua bước summarize_consultation để lưu DB luôn. Phải dùng Prompt răn đe cực gắt mới giữ được luồng hội thoại đi đúng thiết kế ban đầu.