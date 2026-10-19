# PigSkin AI — Giao diện phát hiện bất thường trên da heo

Frontend **React + Vite + Tailwind CSS**, có 4 trang: Tổng quan, Phân tích ảnh, Lịch sử, Thông tin mô hình. Thiết kế xanh dương-trắng, responsive.

## Yêu cầu

- Node.js 20.19+ hoặc 22.12+
- VS Code, terminal và npm

## Chạy giao diện

```bash
npm install
cp .env.example .env
npm run dev
```

Trên Windows PowerShell, dùng `Copy-Item .env.example .env` thay cho `cp`.

Mở địa chỉ Vite hiển thị (mặc định **http://localhost:5173**).

Bản mặc định dùng `VITE_USE_MOCK=true`, vì vậy **không cần backend**. Lưu ý: kết quả dự đoán mô phỏng là **ngẫu nhiên, không được suy diễn thành kết quả AI thật**. Biểu đồ dashboard là dữ liệu minh họa riêng, không tổng hợp từ lịch sử thực.

## Build

```bash
npm run build
npm run preview
```

## Kết nối FastAPI thật

1. Tạo file `.env` tại thư mục gốc và đặt:

```dotenv
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000
```

2. Backend triển khai `POST /predict`, nhận một `UploadFile` tên `file` qua multipart/form-data.
3. Trả JSON ví dụ:

```json
{
  "id": "PIG-1001",
  "label": "Bất thường",
  "confidence": 0.94,
  "abnormal": true,
  "detections": [
    {"label": "Vùng bất thường", "confidence": 0.91, "bbox": [30, 40, 200, 220]}
  ]
}
```

`bbox` có định dạng `[x1,y1,x2,y2]` tính bằng **pixel trên ảnh gốc**. Nếu chưa có detection thì dùng `"detections": []`. Nếu backend trả tọa độ chuẩn hóa (0–1), cần đổi về pixel trước khi hiển thị.

4. Cấu hình CORS cho `http://localhost:5173` trên FastAPI.
5. Khởi động lại `npm run dev` sau khi thay đổi `.env`.

### Backend mẫu để test tích hợp (chưa có AI)

Cài Python packages:

```bash
pip install fastapi uvicorn python-multipart
```

Tạo file `backend_demo.py` **ở thư mục riêng**:

```python
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # CHỈ ĐỂ TEST KẾT NỐI, CHƯA CHẠY MÔ HÌNH AI
    return {
        "label": "Chưa đánh giá (demo)",
        "confidence": 0.0,
        "abnormal": False,
        "detections": []
    }
```

Chạy bằng `uvicorn backend_demo:app --reload --port 8000` trong thư mục chứa file. Giá trị `abnormal: False` ở ví dụ chỉ để đáp ứng cấu trúc API, **không có nghĩa ảnh bình thường**. Hãy thay bằng kết quả AI thật trước khi sử dụng nghiên cứu.

## Lưu ý kỹ thuật

- `src/services/api.js`: chuyển đổi Mock ↔ API thật.
- `src/services/history.jsx`: lưu metadata lịch sử vào localStorage, không lưu ảnh gốc.
- Dữ liệu lịch sử mẫu ở `src/data/mock.js` được nạp lần đầu; nút Xóa lịch sử xóa toàn bộ bản ghi trên trình duyệt.
- Upload: JPG, PNG, WEBP và tối đa 10 MB.
- Không dùng hệ thống này để thay thế chẩn đoán thú y.
