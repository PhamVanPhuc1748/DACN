# Đồ án Chuyên ngành: Ứng dụng Phát hiện Bệnh trên Da Heo

Dự án kết hợp Deep Learning (Computer Vision) và phát triển ứng dụng (Software Engineering) để nhận diện bệnh trên da heo qua hình ảnh.

## Cấu trúc thư mục
- `data/`: Chứa dữ liệu huấn luyện (không push lên git).
- `ml_workspace/`: Source code huấn luyện mô hình học máy.
- `backend/`: API server phục vụ model (FastAPI).
- `mobile_app/`: Source code ứng dụng di động.
- `PigSkinTech/`: Ứng dụng nghiên cứu desktop bằng Flet.
- `docs/`: Tài liệu và báo cáo đồ án.

## Cài đặt môi trường

### 1. Môi trường Học máy (Machine Learning)
```bash
cd ml_workspace
pip install -r requirements.txt
```

### 2. Môi trường Backend (API Server)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Ứng dụng nghiên cứu desktop (Flet)
```powershell
cd PigSkinTech
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Ứng dụng lưu database và ảnh hồ sơ cục bộ; các dữ liệu runtime, dataset và model weights không được commit. Muốn bật suy luận MobileNetV2 cần cung cấp checkpoint tương thích tại `PigSkinTech/models/best.pth` cùng `PigSkinTech/models/classes.json` theo đúng thứ tự nhãn huấn luyện.
