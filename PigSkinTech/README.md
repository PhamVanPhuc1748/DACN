# PigSkinTech AI Studio — Flet Desktop Application

Ứng dụng Desktop hỗ trợ chẩn đoán, thẩm định lâm sàng và quản lý hồ sơ bệnh ngoài da ở heo, xây dựng bằng **Flet**, **PyTorch/TorchVision**, **pyodbc (SQL Server)** và **SQLite**.

---

## 1. Khởi chạy nhanh (PowerShell trong thư mục `PigSkinTech`)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe main.py
```

Hoặc khởi chạy từ thư mục gốc của dự án bằng `..\run_app.bat` hoặc `python ..\run_app.py`.

---

## 2. Các chức năng chính theo phân quyền (RBAC)

- **Giao diện Sáng / Tối (Light & Dark Mode):** Chuyển đổi tức thì trên thanh Sidebar mà không làm mất dữ liệu đang nhập trên biểu mẫu.
- **Người chăn nuôi (`/user`):**
  - Chọn mô hình suy luận thực tế (**MobileNetV2** `20261103_125653` hoặc **EfficientNet-B0** `20261103_125004`).
  - Tải ảnh vùng da heo (`JPG`, `PNG`, `WEBP` tối đa 10 MB) hoặc chọn nhanh từ bộ 5 ảnh mẫu lâm sàng trong `case_images/`.
  - Bật/tắt chế độ **Soi vùng tổn thương AI (Lesion Contrast & Thermal Heatmap)**.
  - Xem kết quả suy luận Tensor Softmax, biểu đồ Top-3 khả năng, biện pháp cách ly và phác đồ điều trị tham khảo.
  - Gửi hồ sơ tới Bác sĩ Thú y thẩm định, hỏi đáp với **Trợ lý AI Thú y (Chatbot)** và **Xuất Phiếu Khám chuẩn 1 trang A4 (`exports/*.html`)**.
- **Bác sĩ Thú y (`/expert`):**
  - Rà soát hàng đợi thẩm định (tự động lọc các ca do người chăn nuôi gửi hoặc ca có độ tin cậy AI `< 75%`).
  - Xác nhận hoặc gán lại nhãn bệnh chuẩn (**Relabeling**) và gửi phác đồ điều trị về cho chủ trại.
  - Duyệt ảnh đã chuẩn hóa nhãn vào kho dữ liệu huấn luyện `curated_dataset/<Class_Name>/`.
  - Thêm/sửa/xóa danh mục bệnh lý & phác đồ điều trị chuẩn (đồng bộ trực tiếp giữa `models/classes.json` và bảng `DiseaseCatalog`).
  - Chạy phân tích hàng loạt (**Batch Inference**) để đánh giá độ nhạy của mô hình.
- **Quản trị viên (`/admin`):**
  - Giám sát thống kê KPI toàn hệ thống, cảnh báo dịch tễ sớm và 3 biểu đồ phân tích trực quan.
  - Quản lý danh sách người dùng (Local & Google OAuth), tìm kiếm, khóa/mở khóa và cấp quyền RBAC.
  - Kích hoạt phiên bản trọng số mô hình `.pt` dùng chung cho toàn hệ thống (đồng bộ với `models/active_model.json` và bảng `ModelVersions`).
  - Kiểm tra kết nối và tự động khởi tạo cơ sở dữ liệu **SQL Server (`PigSkinTechDB`)**, cấu hình **Google OAuth 2.0** và **Gemini API Key**.

---

## 3. Trọng số mô hình & Kết nối dữ liệu

| Kiến trúc | Run đóng gói | Validation Macro-F1 | Test Accuracy | Test Macro-F1 |
|---|---|---:|---:|---:|
| **MobileNetV2** | `models/runs/20261103_125653` | **72.35%** | **64.18%** | **63.55%** |
| **EfficientNet-B0** | `models/runs/20261103_125004` | **71.16%** | **62.69%** | **62.24%** |
| **MobileNetV2** | `models/runs/20261029_161050` | **71.00%** | **62.19%** | **61.25%** |

- Để kết nối thêm thư mục huấn luyện bên ngoài, đặt biến môi trường `PIGSKIN_RESEARCH_ROOT` trước khi chạy ứng dụng:
  ```powershell
  $env:PIGSKIN_RESEARCH_ROOT = 'D:\Research\PigSkinResearchStudio'
  python main.py
  ```

---

## 4. Kiểm thử

```powershell
python -m unittest discover -s tests -v
```
