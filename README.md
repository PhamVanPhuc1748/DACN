# Đồ án Chuyên ngành: Ứng dụng Phát hiện Bệnh trên Da Heo (Desktop App)

Hệ thống ứng dụng Desktop kết hợp Deep Learning (Computer Vision) và FastAPI Backend để chẩn đoán, phát hiện các bệnh da liễu phổ biến ở heo thông qua hình ảnh.

---

## 📂 Cấu trúc thư mục dự án

```text
DACN/
├── backend/               # API Server xử lý tiền xử lý ảnh và chạy suy luận mô hình (FastAPI)
│   ├── app/
│   │   ├── main.py        # Các endpoints (/predict, /health, CORS)
│   │   └── ...
│   └── requirements.txt   # Thư viện phục vụ backend
├── frontend/              # Giao diện ứng dụng Desktop (React + Vite + TailwindCSS)
│   ├── src/
│   │   ├── pages/         # Dashboard, Phân tích (Analyze), Lịch sử (History), Model info
│   │   ├── components/    # Layout, Sidebar, Bounding Box Canvas
│   │   └── services/      # Kết nối API FastAPI & quản lý lịch sử
│   └── package.json
├── ml_workspace/          # Môi trường nghiên cứu & huấn luyện mô hình Deep Learning
│   ├── src/               # data_loader, model, train, evaluate, utils
│   ├── notebooks/         # Jupyter Notebooks thực nghiệm
│   └── weights/           # Trọng số mô hình (.pt, .onnx)
├── data/                  # Dữ liệu ảnh thô và manifest phân chia (không push git)
│   ├── raw/               # Ảnh thô tải về từ Roboflow
│   ├── splits/            # File manifest phân tầng (train.csv, val.csv, test.csv)
│   └── reports/           # Thống kê phân bố nhãn
├── docs/                  # Tài liệu phân tích, kiến trúc hệ thống và báo cáo đồ án
├── run_app.bat            # Script khởi chạy 1-click toàn bộ hệ thống trên Desktop
├── plan.md                # Kế hoạch chi tiết phân chia dataset chống rò rỉ dữ liệu
└── app_roadmap_plan.md    # Kế hoạch phát triển các tính năng ứng dụng thực tế
```

---

## 🚀 Hướng dẫn khởi chạy ứng dụng Desktop

### Cách 1: Khởi chạy 1-click (Khuyên dùng trên Windows)
Chỉ cần nhấp đúp chuột vào file:
👉 **`run_app.bat`**
Hệ thống sẽ tự động bật Backend, bật Frontend và mở giao diện ứng dụng trên trình duyệt máy tính của bạn tại:
- **Giao diện Desktop:** [http://localhost:5173/](http://localhost:5173/)
- **Tài liệu API Swagger:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Cách 2: Khởi chạy thủ công từng phần

#### 1. Khởi động Backend (FastAPI)
```bash
# Kích hoạt môi trường ảo
.\venv\Scripts\activate

# Khởi chạy server FastAPI tại port 8000
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

#### 2. Khởi động Frontend (React / Vite)
```bash
cd frontend
npm install
npm run dev
```
Mở trình duyệt truy cập: `http://localhost:5173/`.
