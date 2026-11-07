# Kế Hoạch Phát Triển Ứng Dụng Desktop Nhận Diện Bệnh Da Heo
## Lộ Trình Tính Năng Để Triển Khai Thực Tế (Production-Ready Roadmap)

> **Mục tiêu:** Xây dựng phần mềm Desktop hỗ trợ kỹ thuật viên thú y và chủ trang trại phát hiện sớm, khoanh vùng và xử lý kịp thời các bệnh da liễu trên đàn heo, có thể chạy ngoại tuyến (Offline), thao tác nhanh và cung cấp giá trị chẩn đoán thực tế.

---

## 1. Phân Tích Thực Tế Triển Khai (Real-world Feasibility)

| Yếu tố thực địa | Thách thức tại trang trại | Giải pháp kiến trúc của ứng dụng |
|:---|:---|:---|
| **Môi trường mạng** | Chuồng trại thường nằm xa trung tâm, internet chập chờn hoặc không có. | **Chạy Offline 100% tại local máy tính** qua FastAPI + ONNX Runtime/TorchScript, không phụ thuộc máy chủ đám mây. |
| **Đối tượng sử dụng** | Kỹ thuật viên chuồng, công nhân chăn nuôi, bác sĩ thú y cơ sở. | Giao diện tối giản, nút bấm to rõ ràng, ngôn ngữ tiếng Việt trực quan, hiển thị màu cảnh báo (Xanh: An toàn, Vàng: Theo dõi, Đỏ: Nguy hiểm). |
| **Dạng bệnh lý da** | Heo thường lấm lem bùn đất, phân, hoặc mắc nhiều bệnh cùng lúc. | Mô hình kết hợp Object Detection (khoanh vùng vết ban/loét) + Báo cáo đa bệnh; có khung vẽ Bounding Box để người dùng kiểm chứng mắt thường. |

---

## 2. Ma Trận Tính Năng Ứng Dụng (Feature Breakdown)

### 📌 Module 1: Phân Tích & Chẩn Đoán Hình Ảnh (Core AI Engine)
- [x] **Tải ảnh đơn lẻ:** Kéo thả hoặc duyệt file ảnh JPG, PNG, WEBP từ máy tính.
- [ ] **Chẩn đoán hàng loạt (Batch Diagnosis):**
  - Tải lên cả thư mục ảnh chụp một dãy chuồng.
  - Hệ thống tự động phân tích lần lượt và xuất bảng tổng kết danh sách các cá thể có dấu hiệu bất thường.
- [ ] **Khoanh vùng tổn thương (Detection Bounding Box):**
  - Đánh dấu chính xác vị trí vết loét, nốt mụn mủ, ban hoại tử trên da heo.
  - Hiển thị mức độ tin cậy (`Confidence Score %`).
- [ ] **Giải thích quyết định mô hình (Explainable AI - Heatmap/Grad-CAM):**
  - Tô màu vùng ảnh có sức ảnh hưởng lớn nhất tới quyết định của AI, giúp người dùng an tâm mô hình không chẩn đoán dựa trên chi tiết nền chuồng trại rác rưởi.
- [ ] **Phân cấp độ khẩn cấp (Triage System):**
  - **Mức độ 1 (Nguy hiểm cao):** Lở mồm long móng (FMD), Đậu heo (Swinepox) -> Báo động cách ly ngay lập tức.
  - **Mức độ 2 (Bệnh mãn tính/nhiễm trùng):** Đóng dấu lợn, Viêm da tiết dịch -> Khuyến cáo dùng kháng sinh/sát trùng.
  - **Mức độ 3 (Ký sinh trùng/môi trường):** Ghẻ, Cháy nắng, Viêm da tiếp xúc -> Vệ sinh môi trường, phun thuốc trị ngoại ký sinh.

---

### 📌 Module 2: Cẩm Nang Bệnh Học & Khuyến Nghị Thú Y (Advisory & Protocol)
- [ ] **Thông tin chi tiết bệnh:**
  - Định nghĩa, tác nhân gây bệnh (vi khuẩn, virus, nấm hay ký sinh trùng).
  - Con đường lây truyền trong chuồng trại.
- [ ] **Khuyến nghị phác đồ sơ cứu bước đầu:**
  - Hướng dẫn cách ly cá thể bệnh để tránh lây nhiễm chéo.
  - Các loại dung dịch sát trùng chuồng trại phù hợp (Iodine, Formol, vôi bột...).
  - Các hoạt chất/thuốc phổ biến theo cẩm nang thú y được phép sử dụng.
  - *Cảnh báo pháp lý:* Nhắc nhở người nuôi tham vấn bác sĩ thú y có chứng chỉ trước khi tiêm thuốc đặc trị.

---

### 📌 Module 3: Quản Lý Đàn & Nhật Ký Điều Trị (Farm Record & History)
- [ ] **Định danh thông tin lâm sàng:**
  - Cho phép người dùng nhập: Mã số tai heo (`Ear Tag`), Số hiệu chuồng (`Pen/Barn ID`), Ngày tuổi/Cân nặng ước tính.
- [ ] **Theo dõi tiến triển điều trị (Follow-up Tracking):**
  - So sánh ảnh chụp ngày thứ 1, ngày thứ 3, ngày thứ 7 để đánh giá vết loét trên da đang lành hay trở nặng.
- [ ] **Lọc & Tìm kiếm lịch sử:**
  - Lọc theo khoảng thời gian, theo loại bệnh, hoặc theo mã chuồng.
- [ ] **Xuất báo cáo (Export Report):**
  - Xuất file **PDF / Excel** gồm ảnh chụp, kết quả chẩn đoán, khuyến nghị điều trị để bàn giao cho chủ trại hoặc nộp cơ quan kiểm dịch.

---

### 📌 Module 4: Tương Tác Chuyên Gia & Hoàn Thiện Mô Hình (Human-in-the-Loop)
- [ ] **Xác nhận / Đính chính của bác sĩ thú y:**
  - Nút *"Đồng ý kết quả"* hoặc *"Bác sĩ sửa lại nhãn"*.
- [ ] **Lưu trữ dữ liệu phản hồi (Active Learning Pool):**
  - Các ca AI chẩn đoán chưa chắc chắn hoặc bị bác sĩ đính chính sẽ được tự động lưu vào thư mục `data/feedback_cases/` kèm nhãn đúng để phục vụ đợt huấn luyện nâng cấp (Fine-tuning) tiếp theo.
- [ ] **Quản lý phiên bản mô hình (Model Registry):**
  - Giao diện cho phép chọn nạp các file trọng số `.pt` hoặc `.onnx` mới khi đội ngũ hoàn tất huấn luyện.

---

### 📌 Module 5: Trải Nghiệm Desktop Hoàn Chỉnh (Desktop Packaging)
- [ ] **Khởi chạy 1-click:** Đã trang bị file `run_app.bat` tự động bật toàn bộ hệ thống và mở trình duyệt.
- [ ] **Đóng gói ứng dụng thành file `.exe` duy nhất:**
  - Sử dụng **Electron** hoặc **Tauri** (kết hợp với backend đóng gói bằng PyInstaller) để tạo bộ cài đặt Windows (`PigSkin-Setup.exe`).
  - Người dùng cuối chỉ cần cài đặt như phần mềm Word/Excel thông thường, hoàn toàn không cần cài Python hay Node.js.

---

## 3. Lộ Trình Triển Khai Theo Từng Sprint

```text
Sprint 1 (Hiện tại): Khung Ứng Dụng & Giao Diện Desktop
├── [x] Xây dựng Backend FastAPI với đầy đủ mock contract, CORS, kiểm tra ảnh
├── [x] Hoàn thiện giao diện React: Dashboard, Phân tích ảnh, Lịch sử, Thông tin Model
├── [x] Đã khởi chạy thành công đồng thời cả Backend (Port 8000) và Frontend (Port 5173)
└── [x] Trang bị script khởi chạy nhanh 1-click: run_app.bat

Sprint 2: Tích Hợp Mô Hình Deep Learning Thật
├── [ ] Chạy pipeline chia dataset chống rò rỉ (dataset_cleaner.py) theo plan.md
├── [ ] Huấn luyện mô hình YOLOv8 / Swin Transformer trên tập train
├── [ ] Đánh giá F1, mAP trên tập test độc lập
└── [ ] Xuất file trọng số best.pt / best.onnx và nạp vào backend/app/main.py

Sprint 3: Nâng Cấp Nghiệp Vụ Thực Tế & Báo Cáo
├── [ ] Tích hợp Cẩm nang phác đồ điều trị thú y theo từng bệnh
├── [ ] Chức năng gắn mã chuồng / mã tai heo và xuất báo cáo PDF
└── [ ] Chức năng phản hồi nhãn (Human-in-the-loop)

Sprint 4: Đóng Gói Thành Phẩm Desktop (.EXE)
├── [ ] Đóng gói Backend thành binary độc lập (PyInstaller)
├── [ ] Đóng gói Desktop Client bằng Tauri / Electron
└── [ ] Thử nghiệm thực địa trên máy tính không có internet
```
