# Individual reflection — Bùi Minh Đức (2A202600005)

## 1. Role
Quản lý kiến trúc mã nguồn, phụ trách merge, xử lý conflict code của các thành viên. UIUX designer + prompt engineer.
 

## 2. Đóng góp cụ thể
- Viết AI Product Canvas trong SPEC
- Config DB, viết script tạo db, chuẩn hóa data
- Viết UIUX cho chatbot
- Quản lý git, tạo branch cho nhóm chuẩn quy trình doanh nghiệp, merge và xử lý conflict code.

## 3. SPEC mạnh/yếu
Mạnh nhất là phần AI Product Canvas và Mini AI Spec, hai phần này xác định rõ ranh giới giữa AI augmentation và automation, đặc biệt là nguyên tắc user xác nhận cuối cùng và logic fallback khi AI không đủ tự tin. Phần Eval Metrics cũng tốt ở chỗ mỗi metric đều có cột Insight giải thích tại sao con số đó quan trọng, không chỉ liệt kê số.

Yếu nhất là phần ROI — các con số lợi nhuận ($150/ngày, $500/ngày) mang tính giả định, chưa có công thức tính ngược từ chi phí vận hành thực tế hay giá trị trung bình một lượt đặt lịch thành công.

## 4. Đóng góp khác
- Viết script test cơ bản cho các tools khi merge.
- Fix các tools get detail khi merge vào không chạy.

## 5. Điều học được
Schema DB là contract của cả nhóm, nếu không lock sớm thì mỗi người sẽ tự diễn giải theo cách riêng và merge sẽ là địa ngục. Lần này học được điều đó theo cách khó nhất. Ngoài ra, khi làm việc với AI để viết tools, cần review output ngay thay vì tin tưởng hoàn toàn — AI hay trả về format đúng nhưng query sai bảng hoặc sai tên cột, lỗi chỉ lộ ra khi chạy thật.


## 6. Nếu làm lại
- Sẽ chuẩn bị format sớm hơn, chốt luôn schema DB và lock lại trước khi các thành viên bắt đầu viết tools. Lần này merge conflict phần lớn đến từ việc mỗi người cầm 1 phiên bản schema khác nhau, không đồng nhất.
- Viết integration test cho từng tool ngay khi tool đó được tạo, không đợi đến lúc merge mới phát hiện tool trả về sai format hoặc query sai bảng.

## 7. AI giúp gì / AI sai gì
- **Giúp:** Xây dựng base, fix tools, viết scripts.
- **Sai/mislead:** Khi lên plan thì AI hay lên plan quá lố với yêu cầu, cần edit lại cho đúng ý mình. 