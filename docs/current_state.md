# Hiện trạng Kiến trúc & Mã nguồn PigSkinTech

Tài liệu phản ánh đúng trạng thái thực tế của mã nguồn trong kho lưu trữ `PigSkinTech` (đã cập nhật đồng bộ với mã nguồn chạy thật).

---

## 1. Kiến trúc Ứng dụng Thực tế

- **Ứng dụng chính (Desktop GUI):** Python **Flet** (`run_app.py` → `PigSkinTech/main.py`) hỗ trợ Light/Dark Mode và phân quyền **RBAC 3 vai trò**:
  - **User / Chủ trại (`/user` — `PigSkinTech/views/user_view.py`):** Tải ảnh đơn / chọn 5 ảnh mẫu lâm sàng thật, suy luận PyTorch, bật **Hội chẩn Kép 2 Mô hình**, soi **Grad-CAM Heatmap**, tính liều lượng thuốc theo cân nặng (`Smart Dosage Calculator`), xem lịch sử khám & in **Phiếu Khám A4 có mã QR**, tra cứu Cẩm nang 10 bệnh và hỏi **Trợ lý AI Thú y (Chatbot)**.
  - **Expert / Bác sĩ Thú y (`/expert` — `PigSkinTech/views/expert_view.py`):** Hàng đợi thẩm định ưu tiên (ca User gửi hoặc confidence `< 75%`), thẩm định & hiệu chỉnh nhãn (`Relabel`) kèm Grad-CAM và Hội chẩn Kép, kê phác đồ trả về User, duyệt ảnh vào Dataset chuẩn (`PigSkinTech/curated_dataset/<class>/`, đủ 10/10 lớp bệnh), CRUD Danh mục Bệnh lý & Phác đồ, chạy kiểm thử hàng loạt (`Batch Inference`).
  - **Admin / Quản trị viên (`/admin` — `PigSkinTech/views/admin_view.py`):** Dashboard KPI (`dbo.vw_DashboardKPIs`) và 3 biểu đồ lâm sàng, quản lý người dùng & RBAC, chuyển đổi trọng số checkpoint `.pt` dùng chung toàn hệ thống (chỉ Admin có quyền ghi đè `active_model.json` & `dbo.ModelVersions`), kiểm thử mô hình đơn lẻ, cấu hình SQL Server, Google OAuth 2.0 và Gemini API.
- **Dịch vụ REST API tùy chọn (`backend/app/main.py`):** FastAPI tái sử dụng trực tiếp pipeline suy luận thật `services/inference.py`, `services/chatbot_service.py` và `services/store.py`; các endpoint quản trị (`/admin/settings`) được bảo vệ bằng xác thực token `ADMIN_API_TOKEN` (`401 Unauthorized` khi thiếu/sai).

---

## 2. Hệ thống AI Deep Learning & Explainable AI

- **Mô hình huấn luyện thật (PyTorch, 10 lớp bệnh da heo trong `PigSkinTech/models/classes.json`):**
  - `MobileNetV2` (`PigSkinTech/models/runs/20261103_125653/best_model.pt`): Validation Macro-F1 **72.35%**, Test Accuracy **64.18%**, Test Macro-F1 **63.55%**.
  - `EfficientNet-B0` (`PigSkinTech/models/runs/20261103_125004/best_model.pt`): Validation Macro-F1 **71.16%**, Test Accuracy **62.69%**, Test Macro-F1 **62.24%**.
  - `MobileNetV2` (`PigSkinTech/models/runs/20261029_161050/best_model.pt`): Phiên bản đối chứng trước đó.
  - Tự động chọn thiết bị `CUDA` và fallback an toàn sang `CPU` nếu máy không có GPU rời; cache tối đa 2 mô hình để phục vụ chế độ Hội chẩn Kép mà vẫn kiểm soát RAM/VRAM.
- **Bộ lọc tiền kiểm tra ảnh Non-Pig / OOD 3 lớp (`PigSkinTech/services/inference.py`):**
  - Kiểm tra tính toàn vẹn file (JPG/PNG/WEBP, ≤ 15 MB, chuẩn hóa RGBA/Grayscale → RGB, hỗ trợ đường dẫn Unicode tiếng Việt).
  - Lớp 0 (kiểm tra nhiễu/ảnh phẳng/ảnh chụp màn hình) + Lớp 1 (ImageNet Pretrained MobileNet + tùy chọn Gemini Vision) + Lớp 2 (ngưỡng Softmax `< 45%` & Shannon Entropy chuẩn hóa `> 0.72`).
  - Ảnh không hợp lệ trả về `is_valid_pig = False`, tuyệt đối **không lưu vào SQL** và **không cho phép gửi Chuyên gia thẩm định**.
- **Explainable AI & Dual-Model (`PigSkinTech/services/inference_service.py`):**
  - `generate_gradcam_heatmap()`: trích xuất feature map & gradient từ `model.features[-1]` tạo bản đồ nhiệt Grad-CAM phủ trong suốt lên ảnh tổn thương.
  - `predict_dual_benchmark()`: chạy song song `MobileNetV2` và `EfficientNet-B0`, trả về bảng đối chiếu nhãn, độ tin cậy %, độ trễ (ms) và Huy hiệu Đồng thuận (`Consensus Badge`).

---

## 3. Cơ sở dữ liệu, Bảo mật & Nghiệp vụ Thú y

- **Cơ sở dữ liệu SQL Server (`PigSkinTechDB` — `PigSkinTech/database_setup.sql`):**
  - Gồm 5 bảng chuẩn (`Users`, `DiseaseCatalog`, `Inspections`, `ChatMessages`, `ModelVersions`) và View thống kê `dbo.vw_DashboardKPIs`, bật `pyodbc.pooling = True` và tự động fallback sang SQLite cục bộ (`PigSkinTech/pigskin_history.db`) nếu dịch vụ SQL Server chưa khởi chạy.
  - Toàn bộ truy vấn sử dụng Parameterized Query (`?`) chống SQL Injection; đồng bộ `DiseaseCatalog` sử dụng cơ chế **UPSERT (`MERGE` / `UPDATE`-or-`INSERT`)** giữ nguyên ID gốc và lưu `updated_by` / `updated_at`.
- **Xác thực & Bảo mật (`PigSkinTech/services/store.py`, `PigSkinTech/services/auth_service.py`):**
  - Băm mật khẩu bằng **PBKDF2-HMAC-SHA256** với salt ngẫu nhiên 16 bytes (`pbkdf2_sha256$<iterations>$<salt>$<hash>`), tương thích ngược và tự động nâng cấp (re-hash) các tài khoản SHA-256 cũ ngay khi đăng nhập.
  - Google OAuth 2.0 Desktop Authorization Code Flow (`http://127.0.0.1:8765/callback`) có kiểm tra CSRF `state` token và tự giải phóng cổng sau đăng nhập.
- **Nghiệp vụ Thú y & Trợ lý AI:**
  - **Smart Dosage Calculator (`PigSkinTech/services/clinical_widgets.py`):** Tính liều thuốc điều trị/hỗ trợ và thuốc sát trùng chuồng theo cân nặng trung bình (kg/con) và số lượng đàn cho đủ 10 lớp bệnh.
  - **Cảnh báo Dịch tễ Sớm (`get_farm_outbreak_alerts`):** Tự động rà soát `dbo.Inspections` và bật Banner cảnh báo an toàn sinh học khi có `≥ 3` ca nguy hiểm mức `Cao`/`Khẩn cấp` tại cùng một trại.
  - **Phiếu Khám A4 có mã QR (`export_vet_report_html`):** Nhúng mã QR chuẩn ISO/IEC 18004 (inline SVG) mã hóa `case_id`, `animal_id`, chẩn đoán và phác đồ; xuất được từ cả màn hình chẩn đoán, thẩm định Expert và Tab Lịch sử khám của User.
  - **Chatbot AI Thú y (`PigSkinTech/services/chatbot_service.py`):** Kết nối Gemini REST API (`gemini-2.5-flash`) với `Strict Domain Guardrail`, fallback an toàn khi thiếu key/lỗi `429`/mất mạng, đồng bộ lịch sử giữa Tab và Popup.

---

## 4. Kiểm thử Tự động

- Bộ kiểm thử tự động nằm tại `PigSkinTech/tests/test_qa_audit.py` và `PigSkinTech/tests/test_theme.py`.
- Chạy kiểm thử bằng Python 3.13:
  ```powershell
  py -3.13 -m unittest discover -s PigSkinTech/tests -v
  ```
