from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Pig Skin Disease Detection API", version="1.0.0")

# Cấu hình CORS để Mobile App có thể gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PredictionResult(BaseModel):
    disease: str
    confidence: float

@app.get("/")
def read_root():
    return {"message": "Welcome to Pig Skin Disease Detection API"}

@app.post("/predict", response_model=PredictionResult)
async def predict(file: UploadFile = File(...)):
    # TODO: Load image, tiền xử lý và đưa vào model Deep Learning để dự đoán
    # Trả về kết quả giả định (Mock data)
    
    filename = file.filename
    print(f"Received file: {filename}")
    
    return {
        "disease": "Lở mồm long móng (FMD - Mock)",
        "confidence": 95.5
    }
