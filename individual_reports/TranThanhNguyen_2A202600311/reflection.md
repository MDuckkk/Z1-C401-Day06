# Individual reflection — Trần Thanh Nguyên (AI202600311)

## 1. Role

Tool engineer. Phụ trách implement các tool backend cho chatbot: `get_doctor_schedule`, `confirm_appointment_summary`, `book_appointment`.

---

## 2. Đóng góp cụ thể

* Xây dựng tool `get_doctor_schedule` để truy vấn và hiển thị lịch khám của bác sĩ từ database
* Implement `confirm_appointment_summary` để tổng hợp và review lại thông tin đặt lịch của bệnh nhân trước khi xác nhận
* Phát triển `book_appointment` để xử lý logic đặt lịch (validate input, check slot, lưu DB)
* Tích hợp các tools vào agent flow để chatbot có thể gọi tool đúng ngữ cảnh
* Debug lỗi liên quan đến tool calling và format input/output giữa LLM và backend

---

## 3. SPEC mạnh/yếu (cụ thể)

* **Mạnh nhất:**

  * **AI Product Canvas rõ Value & Trust:**
    Xác định rõ giá trị cốt lõi là giảm thời gian đặt lịch và tăng khả năng tiếp cận bác sĩ.
    Trust được xử lý bằng việc chỉ trả lời dựa trên data thật từ DB (schedule, slot).

  * **User Stories bao phủ đủ 4 paths:**

    * Happy path: user hỏi → xem lịch → chọn slot → confirm → book
    * Low-confidence: chatbot hỏi lại khi thiếu thông tin (chưa chọn bác sĩ / thời gian)
    * Failure: không có slot → gợi ý ngày khác
    * Correction: user sửa thông tin trước khi confirm

  * **Eval metrics có định hướng product:**

    * Recall cao cho bước gợi ý lịch (tránh bỏ sót slot phù hợp)
    * Precision cao cho bước confirm/booking (tránh đặt sai lịch)
    * Có threshold rõ (VD: >90% booking đúng mới accept)

  * **Failure modes có mitigation cụ thể:**

    * Model hallucination → chỉ cho phép trả lời qua tool (không free text)
    * Slot bị trùng → check DB trước khi insert
    * Thiếu thông tin → force hỏi lại qua prompt

  * **Mini AI spec giúp implement nhanh:**
    Có flow rõ ràng: intent → tool mapping → response format → DB write

---

* **Yếu nhất:**

  * **Chưa handle tốt hallucination ở system level:**
    System prompt chưa đủ chặt → model vẫn có thể tự trả lời thay vì gọi tool
    → thiếu cơ chế hard constraint (tool-only mode)

  * **Thiếu cơ chế verify output của model:**
    Chưa có bước kiểm tra lại kết quả trước khi book (ví dụ: double-check slot availability)

  * **ROI còn mang tính assumption:**
    3 kịch bản chưa khác biệt rõ về input (traffic, adoption rate)
    → khó dùng để ra decision thật

  * **Chưa xử lý concurrency (race condition):**
    Nếu nhiều user book cùng slot → có thể bị double booking

  * **Chưa có fallback khi tool fail:**
    Nếu DB lỗi hoặc tool timeout → chưa có UX xử lý (retry / thông báo user)

---

## 4. Đóng góp khác

* Hỗ trợ team debug các lỗi liên quan đến database và tool integration
* Refactor một số phần code để dễ maintain và mở rộng
* Hỗ trợ kiểm tra luồng end-to-end từ chatbot → tool → database

---

## 5. Điều học được

Cần phải có khả năng tổ chức teammate để mọi người có thể code, fix bug và deploy hiệu quả hơn.
Ngoài ra, nên áp dụng các nguyên tắc SOLID và xây dựng code skeleton từ đầu để:

* Giúp team code nhanh hơn
* Dễ quản lý và maintain
* Giảm lỗi khi integrate giữa các module

---

## 6. Nếu làm lại

Sẽ thiết kế kiến trúc và code skeleton sớm hơn ngay từ đầu dự án.
Đồng thời sẽ:

* Thiết kế strict system prompt ngay từ đầu (tool-first)
* Test failure modes sớm (hallucination, missing slot, invalid input)
* Thêm cơ chế lock slot để tránh race condition

---

## 7. AI giúp gì / AI sai gì

* **Giúp:**
  AI hỗ trợ generate code nhanh cho các function cơ bản và debug lỗi logic
  Giúp đề xuất cách tổ chức code và cải thiện flow tool calling

* **Sai/mislead:**
  Một số gợi ý của AI về implementation không phù hợp với context project (ví dụ: over-engineering hoặc không match với schema DB)
  Bài học: cần validate lại output của AI thay vì sử dụng trực tiếp
