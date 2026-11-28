# PigSkinTech AI Studio — Hệ thống Chẩn đoán & Thẩm định Bệnh Da Heo

**PigSkinTech AI Studio** là ứng dụng Desktop (Flet Material 3, hỗ trợ Light/Dark Mode) kết hợp mô hình thị giác máy tính Deep Learning (**MobileNetV2**, **EfficientNet-B0**, **MobileNetV3-Large**), cơ sở dữ liệu **SQL Server (`pyodbc` Connection Pooling) + SQLite Fallback**, quy trình thẩm định **Human-in-the-Loop** phân quyền 3 vai trò (**User / Expert / Admin**), và **Trợ lý Bác sĩ Thú y AI (Gemini REST API + Strict Domain Guardrail)**.

> ⚠️ **Lưu ý chuyên môn:** Điểm số Softmax của mô hình và câu trả lời từ Trợ lý AI chỉ mang tính chất hỗ trợ sàng lọc bước đầu tại trang trại, không thay thế kết luận chẩn đoán và phác đồ điều trị trực tiếp của Bác sĩ Thú y.

---

## 1. Tính năng nổi bật

- **Phân quyền 3 vai trò (RBAC) & Đăng nhập linh hoạt (`/login`):**
  - Hỗ trợ đăng nhập tài khoản nội bộ (Email/Username + Password), **Đăng nhập nhanh 1-Click** cho 3 vai trò demo và **Google OAuth 2.0 Authorization Code Flow** thực tế (`http://127.0.0.1:8765/callback`).
  - **Người chăn nuôi (`/user`):** Tải ảnh hoặc chọn bộ 5 mẫu thử lâm sàng, chọn mô hình suy luận, bật chế độ **Soi vùng tổn thương AI (Lesion Contrast & Thermal Heatmap)**, xem biểu đồ xác suất **Top-3 Softmax**, nhận hướng dẫn cách ly & phác đồ tham khảo, gửi yêu cầu thẩm định cho Bác sĩ Thú y, hỏi đáp trực tiếp cùng **Chatbot Thú y AI**, và **Xuất Phiếu Khám chuẩn 1 trang A4 (HTML/PDF)**.
  - **Chuyên gia Thú y (`/expert`):** Hàng đợi thẩm định ưu tiên (lọc ca do User gửi hoặc ca có độ tự tin AI `< 75%`), xác nhận hoặc hiệu chỉnh nhãn bệnh (**Relabeling**), kê phác đồ trả về cho chủ trại, duyệt ảnh vào **Kho Dataset chuẩn hóa (`curated_dataset/`)**, quản lý **Danh mục Bệnh lý & Phác đồ**, và chạy **Phân tích hàng loạt (Batch Inference)**.
  - **Quản trị viên (`/admin`):** Bảng điều khiển KPI toàn hệ thống (truy vấn qua View `dbo.vw_DashboardKPIs`) kèm 3 biểu đồ dịch tễ trực quan, cảnh báo dịch tễ sớm khi phát hiện từ 2/10 ca gần nhất thuộc nhóm nguy hiểm cao, quản lý người dùng & cấp quyền RBAC, chuyển đổi trọng số mô hình `.pt` dùng chung toàn hệ thống, và cấu hình kết nối **SQL Server / Google OAuth 2.0 / Gemini API** trực tiếp trên giao diện.
- **Cơ sở dữ liệu Kép (SQL Server + Local SQLite Fallback):**
  - Ưu tiên kết nối **Microsoft SQL Server (`PigSkinTechDB`)** qua `pyodbc` với `Connection Pooling` và tự động khởi tạo database/bảng/view.
  - Nếu máy chưa bật dịch vụ SQL Server tại cổng `1433`, hệ thống tự động chuyển đổi (fallback) liền mạch sang **SQLite cục bộ (`PigSkinTech/pigskin_history.db`)** mà không làm gián đoạn ứng dụng.
- **Trợ lý Bác sĩ Thú y AI (Chatbot Tab & Popup nổi góc phải):**
  - Tích hợp trực tiếp **Google Gemini REST API (`gemini-2.5-flash`)** hoặc OpenAI-compatible/Ollama, tự động nạp toàn bộ danh mục 10 nhóm bệnh lý từ `models/classes.json` và kết quả quét hiện tại vào `VET_SYSTEM_PROMPT`.
  - Cơ chế **Strict Domain Guardrail** từ chối lịch sự các câu hỏi ngoài lề hoặc đùa cợt phi bệnh lý, tự động fallback về cơ sở tri thức lâm sàng nội bộ khi không có khóa API, và đồng bộ tức thì 100% lịch sử hội thoại qua bảng `ChatMessages`.

---

## 2. Danh sách 10 lớp bệnh lý hỗ trợ (`models/classes.json`)

| Mã lớp (Class Code) | Tên bệnh hiển thị (Tiếng Việt) | Mức độ cảnh báo |
|---|---|---|
| `Healthy` | Da khỏe mạnh (Bình thường) | An toàn |
| `Infected_Bacterial_Erysipelas` | Bệnh đóng dấu lợn (Erysipelas) | Cao |
| `Infected_Bacterial_Greasy_Pig_Disease` | Viêm da tiết dịch (Greasy Pig Disease) | Cao |
| `Infected_Environmental_Dermatitis` | Viêm da do môi trường (Dermatitis) | Trung bình |
| `Infected_Environmental_Sunburn` | Cháy nắng da heo (Sunburn) | Thấp |
| `Infected_Fungal_Pityriasis_Rosea` | Bệnh vảy phấn hồng (Pityriasis Rosea) | Thấp |
| `Infected_Fungal_Ringworm` | Bệnh nấm da / Hắc lào (Ringworm) | Trung bình |
| `Infected_Parasitic_Mange` | Bệnh ghẻ Sarcoptes (Mange) | Trung bình / Cao |
| `Infected_Viral_Foot_and_Mouth_Disease` | Lở mồm long móng (FMD) | Khẩn cấp / Cao |
| `Infected_Viral_Swinepox` | Bệnh đậu heo (Swinepox) | Cao |

---

## 3. Trọng số mô hình Deep Learning đóng gói sẵn (`PigSkinTech/models/runs/`)

Phiên bản thử nghiệm **MobileNetV2 — Roboflow Baseline 2026-11-28** có thể chọn trong trang quản lý mô hình. Xem [báo cáo nhóm 5](docs/ban_giao_nhom/BAO_CAO_TUAN_NHOM_5_2026-11-28.md) và [hướng dẫn bàn giao và tái lập](docs/ban_giao_nhom/ROBOFLOW_HANDOFF.md).

Ứng dụng đóng gói sẵn các checkpoint `best_model.pt` (kèm `config.json`, `final_metrics.json`, `history.csv`) huấn luyện trên ảnh chuẩn hóa `224×224` (ImageNet mean/std):

| Kiến trúc | Thư mục Run | Best Epoch | Validation Macro-F1 | Test Accuracy | Test Macro-F1 |
|---|---|---:|---:|---:|---:|
| **MobileNetV2** *(Mặc định)* | `20261103_125653` | 12 | **72.35%** | **64.18%** | **63.55%** |
| **EfficientNet-B0** | `20261103_125004` | 12 | **71.16%** | **62.69%** | **62.24%** |
| **MobileNetV2** *(Bản v4 trước)* | `20261029_161050` | 12 | **71.00%** | **62.19%** | **61.25%** |

- Khi chạy suy luận, `services/inference.py` ưu tiên nạp trọng số trực tiếp trong tiến trình (in-process) với bộ nhớ đệm thread-safe (`_MODEL_RUNTIME_CACHE`), tự động sử dụng GPU (`cuda`) nếu khả dụng và tự động fallback về `cpu` nếu máy không có GPU rời hoặc gặp lỗi CUDA Runtime/OOM.
- Nếu muốn kết nối thêm thư mục huấn luyện bên ngoài, đặt biến môi trường `PIGSKIN_RESEARCH_ROOT` trỏ tới thư mục chứa `ml_workspace/runs`.

---

## 4. Hướng dẫn Cài đặt & Khởi chạy trên Windows

### Bước 1: Tạo môi trường ảo và cài đặt thư viện

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Bước 2: Cấu hình Biến môi trường & Cơ sở dữ liệu (Tùy chọn)

1. Sao chép file mẫu cấu hình:
   ```powershell
   Copy-Item PigSkinTech\.env.example PigSkinTech\.env
   Copy-Item PigSkinTech\config\database.example.json PigSkinTech\config\database.json
   ```
2. Nếu sử dụng **SQL Server**, bạn có thể:
   - Chạy kịch bản [PigSkinTech/database_setup.sql](file:///c:/Users/lelal/Downloads/DACN-devP%20(1)/DACN-devP/PigSkinTech/database_setup.sql) trong SSMS để khởi tạo CSDL `PigSkinTechDB`, 5 bảng (`Users`, `DiseaseCatalog`, `Inspections`, `ChatMessages`, `ModelVersions`), các Covering Indexes và View `dbo.vw_DashboardKPIs`; **hoặc**
   - Mở tab **Cấu hình hệ thống** trong tài khoản **Admin** và bấm **"🔌 Kiểm tra & tạo database"** để ứng dụng tự động tạo database và bảng.
3. Điền `GEMINI_API_KEY` vào `PigSkinTech/.env` (hoặc nhập trong tab Cấu hình hệ thống của Admin) nếu muốn bật phản hồi trực tuyến từ `gemini-2.5-flash`.

### Bước 3: Khởi chạy ứng dụng Desktop

Cách 1 — Chạy qua script Batch hoặc Launcher ở thư mục gốc:
```powershell
.\run_app.bat
# Hoặc:
python run_app.py
```

Cách 2 — Chạy trực tiếp trong thư mục `PigSkinTech`:
```powershell
cd PigSkinTech
python main.py
```

### Tài khoản demo

Đặt `PIGSKIN_DEMO_PASSWORD` trong `PigSkinTech/.env` trước khi khởi động CSDL demo. Ứng dụng tạo các tài khoản còn thiếu và giữ mật khẩu hiện có.

| Vai trò | Email đăng nhập | Username | Đường dẫn (Route) |
|---|---|---|---|
| **Người chăn nuôi (User)** | `nongdan.pigskin@gmail.com` | `nongdan` | `/user` |
| **Bác sĩ Thú y (Expert)** | `bs.thuy.pigskin@gmail.com` | `bsthuy` | `/expert` |
| **Quản trị viên (Admin)** | `admin.pigskin@gmail.com` | `admin` | `/admin` |

---

## 5. Kiểm thử Tự động (Unit & Integration Tests)

Chạy bộ kiểm thử tự động kiểm tra giao diện Sáng/Tối, độ tương phản văn bản, đồng bộ CSDL (`store.py`), cơ chế fallback của Chatbot (`chatbot_service.py`) và thuật toán tạo bản đồ nhiệt (`generate_lesion_heatmap`):

```powershell
python -m unittest discover -s PigSkinTech/tests -v
```

---

## 6. Cấu trúc Thư mục Chính

```text
DACN-devP/
├── run_app.bat                        # Script khởi động nhanh trên Windows
├── run_app.py                         # Python launcher tự động nhận diện venv/.venv
├── requirements.txt                   # Danh sách thư viện Python chuẩn
├── README.md                          # Tài liệu tổng quan dự án
├── backend/                           # Dịch vụ FastAPI REST API phụ trợ
│   ├── .env.example                   # Mẫu biến môi trường cho Backend & SQL/AI
│   └── app/                           # Các module API (main.py, config.py, database.py)
└── PigSkinTech/                       # Ứng dụng Desktop chính (Flet Material 3)
    ├── .env.example                   # Mẫu cấu hình môi trường cho Desktop App
    ├── database_setup.sql             # Kịch bản khởi tạo & đồng bộ SQL Server (PigSkinTechDB)
    ├── main.py                        # Điểm vào ứng dụng Flet & bộ định tuyến RBAC
    ├── theme.py                       # Hệ thống Design System & bảng màu Light/Dark
    ├── config/
    │   └── database.example.json      # Mẫu cấu hình kết nối máy chủ SQL Server
    ├── case_images/                   # Kho ảnh ca bệnh thực tế & bộ 5 ảnh mẫu lâm sàng
    ├── models/
    │   ├── classes.json               # Danh mục 10 lớp bệnh lý & phác đồ điều trị chuẩn
    │   └── runs/                      # Các phiên bản checkpoint best_model.pt đóng gói sẵn
    ├── services/
    │   ├── auth_service.py            # Xác thực Local/Google OAuth, A4 HTML Report, Heatmap, Sidebar Shell
    │   ├── chat_widget.py             # Giao diện khung Chatbox Tab & Popup nổi đồng bộ
    │   ├── chatbot_service.py         # Dịch vụ Gemini REST API, Domain Guardrail & Clinical Fallback
    │   ├── clinical_widgets.py        # Biểu đồ thống kê dịch tễ & Modal CRUD danh mục bệnh lý
    │   ├── config_store.py            # Đọc/ghi đồng bộ cấu hình .env và config/database.json
    │   ├── inference.py               # Tiền xử lý ảnh, nạp PyTorch checkpoint & suy luận Softmax
    │   ├── inference_worker.py        # Worker suy luận độc lập kèm cơ chế fallback CUDA -> CPU
    │   ├── project_data.py            # Quản lý phiên bản model runs, metrics, manifest & classes.json
    │   └── store.py                   # Tầng lưu trữ hợp nhất SQL Server (pyodbc) & SQLite cục bộ
    ├── views/
    │   ├── auth_view.py               # Màn hình đăng nhập (/login)
    │   ├── user_view.py               # Không gian Người chăn nuôi (/user)
    │   ├── expert_view.py             # Không gian Chuyên gia Thú y (/expert)
    │   ├── admin_view.py              # Không gian Quản trị hệ thống (/admin)
    │   └── profile_view.py            # Quản lý hồ sơ cá nhân, ảnh đại diện & đổi mật khẩu
    └── tests/
        └── test_theme.py              # Kiểm thử tự động giao diện, CSDL, Chatbot & Heatmap
```
