# KẾ HOẠCH BỔ SUNG & HOÀN THIỆN CÁC CHỨC NĂNG DỰ ÁN
## Đồ Án: Ứng Dụng Desktop Phát Hiện Bệnh Trên Da Heo Bằng Deep Learning

> **Mục tiêu:** Nâng cấp hệ thống từ mức demo cơ bản thành một **ứng dụng Desktop hoàn chỉnh, chuyên nghiệp**, vừa đáp ứng xuất sắc các tiêu chí đánh giá đồ án công nghệ, vừa giải quyết trọn vẹn bài toán thực tế của kỹ thuật viên thú y và chủ trang trại chăn nuôi heo.

---

## I. Đánh Giá Hiện Trạng & Khoảng Trống Chức Năng (Gap Analysis)

| Thành phần | Trạng thái hiện tại | Những điểm còn thiếu để áp dụng thực tế |
|---|---|---|
| **Chẩn đoán (Analyze)** | Chỉ tải được **1 ảnh đơn lẻ**, trả về 1 kết quả cơ bản. | ❌ Chưa có phân tích hàng loạt (Batch).<br>❌ Chưa chỉnh được ngưỡng tin cậy (Confidence threshold).<br>❌ Chưa hỗ trợ chụp trực tiếp từ Camera/Webcam.<br>❌ Chưa có phác đồ điều trị đi kèm. |
| **Lịch sử (History)** | Lưu tạm vào `localStorage` trình duyệt, dữ liệu mất khi xóa cache. | ❌ Chưa lưu vào Cơ sở dữ liệu (SQLite).<br>❌ Chưa có tìm kiếm, lọc theo mã chuồng, thời gian.<br>❌ Chưa thể xuất báo cáo chẩn đoán (PDF / Excel). |
| **Bệnh học (Medical)** | Chỉ hiện tên bệnh tiếng Anh/Việt vắn tắt. | ❌ Thiếu cẩm nang chi tiết: nguyên nhân, triệu chứng, mức độ lây lan, thuốc sát trùng và cách ly. |
| **Quản lý Đàn (Farm)** | Không có thông tin ngữ cảnh chuồng trại. | ❌ Không gắn được Mã số tai heo (`Ear Tag`), Mã dãy chuồng (`Pen ID`), Nhật ký theo dõi tiến triển vết thương. |
| **Mô hình (Model / AI)** | Màn hình giới thiệu tĩnh. | ❌ Chưa có chức năng chọn/chuyển đổi file trọng số (.pt / .onnx).<br>❌ Chưa có chức năng bác sĩ đính chính kết quả (Human-in-the-Loop). |

---

## II. Danh Mục Các Chức Năng Cần Bổ Sung (Phân Cấp Ưu Tiên)

### 🔴 NHÓM 1: CÁC CHỨC NĂNG CỐT LÕI (Ưu tiên P0 - Bắt buộc để bảo vệ đồ án)

#### 1. Chẩn đoán Hàng Loạt (Batch Diagnosis)
- **Ý nghĩa thực tế:** Trang trại có hàng trăm con heo; người nuôi đi kiểm tra chuồng sẽ chụp 10 - 30 ảnh liên tục. Bắt buộc phải có chức năng tải lên nhiều ảnh cùng lúc.
- **Mô tả chức năng:**
  - Kéo thả cả thư mục hoặc chọn nhiều file ảnh (JPG, PNG).
  - Thanh tiến trình phân tích tự động: `Đang xử lý ảnh 5/20...`.
  - Hiển thị bảng tổng hợp kết quả: Số ca bất thường, tỷ lệ bệnh, gắn nhãn màu cảnh báo từng ảnh.
  - Cho phép bấm vào từng ảnh trong danh sách để xem chi tiết vùng tổn thương (Bounding Box).

#### 2. Cẩm Nang Bệnh Học & Hướng Dẫn Điều Trị Thú Y (Disease Knowledge Base)
- **Ý nghĩa thực tế:** Chẩn đoán ra tên bệnh chưa đủ, người nuôi cần biết ngay *"Bệnh này có lây không?", "Xử lý thế nào?", "Cần cách ly không?"*.
- **Mô tả chức năng:**
  - Thêm một trang mới: **`Cẩm nang bệnh học`** (hoặc tab sổ tay tra cứu).
  - Tích hợp sẵn cơ sở tri thức của **9 bệnh da heo** trong dataset:
    1. *Bệnh đóng dấu lợn (Erysipelas)*
    2. *Viêm da tiết dịch (Greasy Pig Disease)*
    3. *Lở mồm long móng (FMD - Báo động khẩn)*
    4. *Bệnh đậu lợn (Swinepox)*
    5. *Bệnh ghẻ sảy (Mange)*
    6. *Bệnh nấm da (Ringworm)*
    7. *Bệnh vảy phấn hồng (Pityriasis Rosea)*
    8. *Viêm da dị ứng/môi trường (Dermatitis)*
    9. *Cháy nắng da heo (Sunburn)*
  - Khi chẩn đoán ra bệnh ở trang Analyze, có nút bấm: **`Xem phác đồ điều trị & hướng dẫn cách ly`** nhảy thẳng đến thông tin bệnh tương ứng.

#### 3. Phân Cấp Mức Độ Nguy Hiểm & Báo Động Khẩn Cấp (Triage System)
- **Hệ thống 3 cấp độ màu sắc cảnh báo:**
  - 🚨 **Cấp 1 - ĐỎ (Nguy hiểm cấp tính - Lây lan toàn trại):** Lở mồm long móng, Đậu lợn -> Bật pop-up đỏ cảnh báo yêu cầu cách ly toàn bộ dãy chuồng ngay lập tức.
  - ⚠️ **Cấp 2 - VÀNG (Nhiễm trùng vi khuẩn/nấm):** Đóng dấu lợn, Viêm da tiết dịch, Nấm -> Khuyến cáo dùng kháng sinh và sát trùng chuồng trại.
  - ℹ️ **Cấp 3 - XANH/XÁM (Ký sinh trùng & Da do môi trường):** Ghẻ, Viêm da môi trường, Cháy nắng -> Khuyến cáo vệ sinh, phun thuốc trị ký sinh.

#### 4. Lưu Trữ Dữ Liệu Bằng SQLite (Persistent Database)
- **Thay thế localStorage:** Xây dựng cơ sở dữ liệu SQLite nhẹ tích hợp trong Backend FastAPI (file `backend/pigskin.db`).
- **Lợi ích:**
  - Lưu trữ vĩnh viễn lịch sử các lần chẩn đoán kèm ảnh, ngày giờ, thông tin chuồng.
  - Dữ liệu không bị mất khi đổi máy hoặc xóa bộ nhớ tạm trình duyệt.

---

### 🟡 NHÓM 2: CHỨC NĂNG NÂNG TẦM ĐỒ ÁN (Ưu tiên P1 - Tạo ấn tượng vượt trội)

#### 5. Xuất Phiếu Kết Quả Chẩn Đoán (Export PDF & Excel)
- **Ý nghĩa thực tế:** Kỹ thuật viên chuồng cần in phiếu hoặc xuất file gửi cho chủ trại và bác sĩ thú y để ký duyệt mua thuốc.
- **Mô tả chức năng:**
  - Xuất phiếu khám dạng **PDF**: Có logo hệ thống, ảnh gốc, ảnh khoanh vùng bệnh, tên bệnh, độ tin cậy, thông tin chuồng/tai heo, và khuyến nghị y tế.
  - Xuất file **Excel**: Danh sách thống kê tình hình bệnh của đàn heo phục vụ báo cáo quản trị trại.

#### 6. Gắn Thẻ Định Danh Lâm Sàng (Ear Tag & Pen Management)
- Cho phép người dùng nhập thông tin trước/sau khi phân tích:
  - **Mã số tai heo (Ear Tag ID):** ví dụ `HEO-0142`
  - **Dãy chuồng (Pen / Barn ID):** ví dụ `Chuồng A3`
  - **Ghi chú của người nuôi:** ví dụ *"Heo biếng ăn, sốt 40 độ từ hôm qua"*.

#### 7. Thanh Trượt Tùy Chỉnh Ngưỡng Tin Cậy (Confidence Slider)
- Cho phép người dùng kéo thanh trượt từ `0.10` đến `0.95`.
- Vùng nhận diện trên ảnh (Bounding Box) tự động ẩn/hiện theo mức ngưỡng được chọn, giúp kỹ thuật viên linh hoạt kiểm tra cả các dấu hiệu bệnh mờ nhạt.

#### 8. Hỗ Trợ Chụp Ảnh Trực Tiếp Từ Webcam / Camera Ngoài
- Tích hợp nút **`Mở Camera`** trên Desktop:
  - Kết nối webcam máy tính hoặc camera nội soi USB để chụp trực tiếp vết da heo mà không cần dùng điện thoại chụp rồi copy sang máy tính.

---

### 🟢 NHÓM 3: CHỨC NĂNG CHUYÊN SÂU & MỞ RỘNG (Ưu tiên P2 - Hoàn thiện ứng dụng)

#### 9. Chức Năng Bác Sĩ Đính Chính (Human-in-the-Loop Feedback)
- Khi AI dự đoán, bên cạnh kết quả có 2 nút:
  - `[✓ Xác nhận đúng]`
  - `[✎ Sửa chẩn đoán]`: Bác sĩ thú y chọn lại tên bệnh đúng từ danh sách.
- Toàn bộ các ca sửa này sẽ được lưu riêng vào bảng `feedback_cases` để nhóm AI dùng re-train phiên bản mô hình tiếp theo.

#### 10. So Sánh Tiến Triển Vết Bệnh (Follow-up Progress Comparison)
- Cho phép chọn 2 bức ảnh của cùng 1 cá thể heo ở 2 thời điểm khác nhau (ví dụ: *Ngày 1 khi mới phát hiện* vs *Ngày 5 sau khi bôi thuốc*).
- Hiển thị song song (Side-by-side) để đánh giá vết thương đang lành hay đang lan rộng.

#### 11. Quản Lý Phiên Bản Trọng Số Mô Hình (Model Switcher)
- Trong trang Model, cho phép:
  - Xem danh sách các file model trong `ml_workspace/weights/` (`yolov8_pigskin.pt`, `resnet50_best.pt`, `model_v2.onnx`).
  - Nút bấm `[Kích hoạt Model này]` để chuyển đổi mô hình suy luận trong backend mà không cần khởi động lại server.

---

## III. Thiết Kế Kiến Trúc & Luồng Dữ Liệu Mới

```text
[ Desktop Frontend (React / Vite) ]
   │
   ├── 1. Analyze Page      ──> Upload đơn/hàng loạt, Camera, chỉnh Confidence
   ├── 2. Disease Guide     ──> Cẩm nang 9 bệnh da heo & phác đồ điều trị
   ├── 3. History & Export  ──> Tìm kiếm, lọc theo Pen ID, Xuất PDF/Excel
   ├── 4. Model Registry    ──> Đổi trọng số, chỉ số thực nghiệm mAP/F1
   │
   ▼ HTTP REST API
[ FastAPI Backend Engine (Port 8000) ]
   │
   ├── /predict             ──> Dự đoán ảnh đơn / mảng ảnh
   ├── /diseases            ──> Cung cấp cẩm nang và phác đồ thú y
   ├── /history             ──> Lấy và lọc lịch sử chẩn đoán
   ├── /export/pdf          ──> Sinh phiếu chẩn đoán y tế
   └── /models/switch       ──> Nạp trọng số mô hình mới
   │
   ▼
[ SQLite Database: backend/pigskin.db ]
   ├── Bảng `records`: id, image_path, ear_tag, pen_id, disease, confidence, created_at
   ├── Bảng `diseases`: code, name, danger_level, treatment, biosecurity
   └── Bảng `feedbacks`: record_id, corrected_disease, doctor_note
```

---

## IV. Lộ Trình Triển Khai Chi Tiết (Theo 3 Giai Đoạn)

### 🚀 Giai Đoạn 1: Hoàn thiện tính năng lâm sàng & Cẩm nang thú y (1 - 2 ngày tới)
1. Thêm trang **Cẩm nang 9 bệnh da heo (`DiseasesGuide.jsx`)** với phác đồ điều trị, thuốc và cách ly chuẩn thú y.
2. Nâng cấp trang **Phân tích (`Analyze.jsx`)**:
   - Thêm thanh trượt ngưỡng tin cậy (`Confidence Slider`).
   - Thêm ô nhập mã chuồng (`Pen ID`) và mã tai (`Ear Tag`).
   - Thêm bảng cảnh báo mức độ khẩn cấp (Cảnh báo Đỏ / Vàng / Xanh).
3. Kết nối liên kết từ kết quả chẩn đoán sang cẩm nang điều trị tương ứng.

### 🚀 Giai Đoạn 2: Nâng cấp Cơ sở dữ liệu SQLite & Xuất báo cáo PDF (2 - 3 ngày tới)
1. Cấu hình SQLite trong FastAPI (`backend/app/database.py`).
2. Viết API lưu trữ lịch sử thật và truy vấn theo mã chuồng, thời gian.
3. Tích hợp thư viện xuất báo cáo (Xuất phiếu chẩn đoán PDF và Excel).
4. Bổ sung tính năng phân tích ảnh hàng loạt (`Batch Upload`).

### 🚀 Giai Đoạn 3: Tích hợp AI thật & Hoàn thiện sản phẩm (Sau khi train xong model)
1. Huấn luyện mô hình YOLOv8 trên tập dữ liệu đã chuẩn hóa (theo `plan.md`).
2. Nạp file trọng số thật vào Backend.
3. Thêm tính năng Human-in-the-loop (Bác sĩ đính chính kết quả).
4. Đóng gói ứng dụng thành file chạy độc lập (.exe).
