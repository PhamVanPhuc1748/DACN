import io
import logging
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PigSkinAPI")

app = FastAPI(
    title="Pig Skin Disease Detection API",
    description="Backend API phục vụ nhận diện và chẩn đoán bệnh da heo cho Desktop App",
    version="1.0.0"
)

# Cấu hình CORS để Desktop UI (Vite / React) có thể gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DetectionItem(BaseModel):
    label: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]

class PredictionResult(BaseModel):
    disease: str
    confidence: float
    detections: Optional[List[DetectionItem]] = []

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Pig Skin Disease Detection API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/predict", response_model=PredictionResult)
async def predict(file: UploadFile = File(...)):
    """
    Tiếp nhận ảnh từ ứng dụng Desktop, kiểm tra định dạng và trả về kết quả chẩn đoán.
    (Hiện tại trả về kết quả chẩn đoán mô phỏng chuẩn xác định dạng,
     sẵn sàng nạp trọng số mô hình PyTorch / YOLO khi hoàn tất huấn luyện).
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File tải lên bắt buộc phải là định dạng hình ảnh (JPG, PNG, WEBP).")

    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        width, height = image.size
        logger.info(f"Đã nhận file: {file.filename} (Kích thước: {width}x{height})")
    except Exception as e:
        logger.error(f"Lỗi khi đọc file ảnh: {e}")
        raise HTTPException(status_code=400, detail="Không thể giải mã file ảnh tải lên.")

    # Tọa độ bounding box mẫu tính toán tương đối theo kích thước ảnh thật
    # (Để nút test trên giao diện Desktop hiển thị trực quan ngay lập tức)
    bx1 = int(width * 0.25)
    by1 = int(height * 0.25)
    bx2 = int(width * 0.75)
    by2 = int(height * 0.75)

    # TODO: Khi mô hình thật (YOLOv8/ResNet) sẵn sàng:
    # results = model(image)
    # return parse_real_results(results)

    return {
        "disease": "Bệnh đóng dấu lợn (Erysipelas - Demo Mode)",
        "confidence": 94.6,
        "detections": [
            {
                "label": "Tổn thương da hình quả trám",
                "confidence": 0.93,
                "bbox": [bx1, by1, bx2, by2]
            }
        ]
    }
