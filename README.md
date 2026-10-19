# Đồ án Chuyên ngành: Ứng dụng Phát hiện Bệnh trên Da Heo

Dự án kết hợp Deep Learning (Computer Vision) và phát triển ứng dụng (Software Engineering) để nhận diện bệnh trên da heo qua hình ảnh.

## Cấu trúc thư mục
- `data/`: Chứa dữ liệu huấn luyện (không push lên git).
- `ml_workspace/`: Source code huấn luyện mô hình học máy.
- `backend/`: API server phục vụ model (FastAPI).
- `mobile_app/`: Source code ứng dụng di động.
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
