# Đồ án Chuyên ngành: Ứng dụng Phát hiện Bệnh trên Da Heo (Desktop App)

Hệ thống ứng dụng Desktop nguyên bản (Python Flet) kết hợp Deep Learning (Computer Vision) để chẩn đoán, phát hiện các bệnh da liễu phổ biến ở heo thông qua hình ảnh.

---

## 📂 Cấu trúc thư mục dự án

```text
DACN/
├── PigSkinTech/           # Ứng dụng Desktop chính (Flet Desktop UI từ devN)
│   ├── main.py            # Giao diện chính (Tổng quan, Phân tích ảnh, Lịch sử, Dataset, Huấn luyện, Mô hình)
│   ├── services/
│   │   ├── inference.py   # Module nạp trọng số MobileNetV2 và chạy suy luận ảnh
│   │   └── store.py       # Cơ sở dữ liệu SQLite cục bộ (pigskin_history.db) và lưu trữ ảnh ca bệnh
│   ├── models/            # Trọng số mô hình (.pth) và danh sách nhãn classes.json
│   ├── requirements.txt   # Thư viện phục vụ Desktop App (flet, Pillow, torch, torchvision)
│   └── README.md
├── backend/               # API Server dự phòng (FastAPI)
│   ├── app/
│   │   ├── main.py        # Các endpoints (/predict, /health)
│   │   └── ...
│   └── requirements.txt
├── ml_workspace/          # Môi trường nghiên cứu & huấn luyện mô hình Deep Learning
│   ├── notebooks/         # Jupyter Notebooks thực nghiệm
│   └── weights/           # Trọng số mô hình (.pt, .onnx)
├── data/                  # Dữ liệu ảnh thô và manifest phân chia (không push git)
│   ├── raw/               # Ảnh thô tải về từ Roboflow
│   ├── splits/            # File manifest phân tầng (train.csv, val.csv, test.csv)
│   └── reports/           # Thống kê phân bố nhãn
├── docs/                  # Tài liệu phân tích, kiến trúc hệ thống và báo cáo đồ án
├── run_app.bat            # Script khởi chạy 1-click ứng dụng Desktop (Flet)
└── run_app.py             # Script Python khởi chạy ứng dụng Desktop
```

---

## 🚀 Hướng dẫn khởi chạy ứng dụng Desktop

### Cách 1: Khởi chạy 1-click (Khuyên dùng trên Windows)
Chỉ cần nhấp đúp chuột vào file:
👉 **`run_app.bat`**
Hệ thống sẽ tự động khởi chạy giao diện Desktop **PigSkin AI Studio** (Flet).

### Cách 2: Khởi chạy bằng lệnh qua Terminal
```powershell
# Kích hoạt môi trường và chạy trực tiếp
.\venv\Scripts\python.exe run_app.py

# Hoặc chạy từ trong thư mục PigSkinTech:
cd PigSkinTech
..\venv\Scripts\python.exe main.py
```

---

## 💡 Điểm nổi bật của giao diện Desktop (Flet)
1. **Giao diện Command Center:** Hỗ trợ chuyển đổi mượt mà giữa 2 giao diện Sáng (Light) và Tối (Dark).
2. **Quản lý ca bệnh hoàn chỉnh:** Nhập mã số heo (Ear Tag), trang trại, vị trí vết thương, ngày khởi phát và các triệu chứng lâm sàng.
3. **Lưu trữ cục bộ:** Tự động tạo bản sao lưu ảnh gốc vào `case_images/` và lưu trữ lịch sử kiểm tra trong SQLite `pigskin_history.db`.
4. **Hỗ trợ suy luận trực tiếp:** Sẵn sàng tích hợp trọng số MobileNetV2 (`models/best.pth` và `models/classes.json`).
