from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import ROOT, UPLOADS, init_db
from .routes import admin, cases, dashboard, dataset, diagnose, models


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Pig Skin Disease Detection API", version="1.0.0", lifespan=lifespan)

# Cấu hình CORS để Web/Mobile App có thể gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (diagnose, cases, dataset, models, dashboard, admin):
    app.include_router(r.router)

# ponytail: ảnh upload & experiments phục vụ công khai (tên file = sha256, khó đoán);
# chuyển sang endpoint có auth nếu dữ liệu trại cần bảo mật.
UPLOADS.mkdir(parents=True, exist_ok=True)
(ROOT / "ml_workspace" / "experiments").mkdir(parents=True, exist_ok=True)
app.mount("/files/uploads", StaticFiles(directory=UPLOADS), name="uploads")
app.mount("/files/experiments", StaticFiles(directory=ROOT / "ml_workspace" / "experiments"), name="experiments")


@app.get("/")
def read_root():
    return {"message": "Welcome to Pig Skin Disease Detection API", "docs": "/docs"}
