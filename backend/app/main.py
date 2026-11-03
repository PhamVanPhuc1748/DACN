import io
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from app.database import get_feedback, get_record, get_records, save_feedback, save_record
from app.diseases_data import DISEASES_DATA

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PigSkinAPI")

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
WEIGHTS_DIR = BASE_DIR.parent / "ml_workspace" / "weights"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_BATCH_FILES = 30

app = FastAPI(
    title="Pig Skin Disease Detection API",
    description="API nghiên cứu để phân tích ảnh da heo, tra cứu bệnh và lưu hồ sơ theo dõi.",
    version="1.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


class FeedbackRequest(BaseModel):
    record_id: str
    doctor_status: Literal["CONFIRMED", "CORRECTED"]
    corrected_disease_code: Optional[str] = None
    doctor_notes: Optional[str] = Field(default=None, max_length=2000)


class ModelSwitchRequest(BaseModel):
    filename: str


@app.get("/")
def read_root():
    return {"status": "online", "service": "PigSkin API", "version": "1.2.0", "database": "SQLite", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "SQLite"}


@app.get("/diseases")
def list_diseases():
    return list(DISEASES_DATA.values())


@app.get("/diseases/{code}")
def get_disease_detail(code: str):
    disease = DISEASES_DATA.get(code.upper())
    if not disease:
        raise HTTPException(status_code=404, detail="Không tìm thấy bệnh theo mã đã yêu cầu.")
    return disease


def serialize_record(record: dict):
    image_path = record.get("image_path", "")
    record["image_url"] = f"/uploads/{Path(image_path).name}" if image_path else None
    return record


@app.get("/records")
def list_diagnostic_records(
    limit: int = Query(100, ge=1, le=200),
    pen_id: Optional[str] = None,
    ear_tag: Optional[str] = None,
    disease_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    q: Optional[str] = None,
):
    return [serialize_record(record) for record in get_records(limit, pen_id, disease_code, ear_tag, start_date, end_date, q)]


@app.get("/records/{record_id}")
def get_diagnostic_record(record_id: str):
    record = get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ phân tích.")
    return serialize_record(record)


def _save_upload_image(image: Image.Image, record_id: str):
    filename = f"{record_id.lower()}.webp"
    image.convert("RGB").save(UPLOAD_DIR / filename, "WEBP", quality=88, method=5)
    return f"uploads/{filename}"


def _demo_disease_code(filename: str):
    name = Path(filename or "").name.lower()
    matchers = {
        "VIRA_FMD": ("fmd", "mong"), "VIRA_POX": ("pox", "dau"),
        "PARA_MANGE": ("mange", "ghe"), "BACT_GPD": ("gpd", "tiet_dich"),
        "FUNG_RING": ("ringworm",), "FUNG_ROSEA": ("rosea",),
        "ENV_DERM": ("dermatitis", "derm"), "ENV_SUN": ("sunburn",),
        "HEALTHY": ("healthy", "khoe"),
    }
    for code, keys in matchers.items():
        if any(key in name for key in keys):
            return code
    return "BACT_ERY"


async def _read_upload(file: UploadFile):
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="Chỉ nhận ảnh JPG, PNG hoặc WEBP.")
    contents = await file.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh vượt quá dung lượng tối đa 10 MB.")
    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Không thể đọc ảnh. Hãy chọn một tệp JPG, PNG hoặc WEBP hợp lệ.")
    return image


def _create_prediction(image: Image.Image, filename: str, ear_tag: Optional[str], pen_id: Optional[str], notes: Optional[str], threshold: float):
    record_id = f"PIG-{uuid.uuid4().hex[:12].upper()}"
    code = _demo_disease_code(filename)
    disease = DISEASES_DATA[code]
    healthy = code == "HEALTHY"
    confidence = 0.982 if healthy else 0.948
    width, height = image.size
    detections = []
    if not healthy and confidence >= threshold:
        detections.append({
            "label": f"Vùng da cần quan sát · {disease['name_vi']}",
            "confidence": confidence,
            "bbox": [int(width * .22), int(height * .25), int(width * .78), int(height * .8)],
        })
    created_at = datetime.now(timezone.utc).isoformat()
    image_path = _save_upload_image(image, record_id)
    record = {
        "id": record_id,
        "filename": Path(filename or "anh-tai-len").name,
        "image_path": image_path,
        "image_url": f"/uploads/{Path(image_path).name}",
        "ear_tag": (ear_tag or "").strip(),
        "pen_id": (pen_id or "").strip(),
        "disease_code": code,
        "disease_name": disease["name_vi"],
        "confidence": confidence,
        "urgency_level": disease["urgency_level"],
        "urgency_label": disease["urgency_label"],
        "treatment_summary": disease.get("care_summary", ""),
        "abnormal": not healthy,
        "detections": detections,
        "notes": (notes or "").strip(),
        "source": "Mô phỏng theo tên tệp · chưa nạp mô hình AI",
        "created_at": created_at,
    }
    save_record(record)
    return {key: value for key, value in record.items() if key != "image_path"}


@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    ear_tag: Optional[str] = Form(None),
    pen_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    threshold: float = Form(0.5, ge=0.1, le=0.95),
):
    image = await _read_upload(file)
    logger.info("Received %s (%sx%s), ear=%s, pen=%s", file.filename, image.width, image.height, ear_tag, pen_id)
    return _create_prediction(image, file.filename or "", ear_tag, pen_id, notes, threshold)


@app.post("/predict/batch")
async def predict_batch(
    files: List[UploadFile] = File(...),
    ear_tag: Optional[str] = Form(None),
    pen_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    threshold: float = Form(0.5, ge=0.1, le=0.95),
):
    if not files:
        raise HTTPException(status_code=400, detail="Hãy chọn ít nhất một ảnh.")
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(status_code=413, detail=f"Mỗi lượt chỉ nhận tối đa {MAX_BATCH_FILES} ảnh.")
    results = []
    for file in files:
        try:
            image = await _read_upload(file)
            result = _create_prediction(image, file.filename or "", ear_tag, pen_id, notes, threshold)
            results.append({"ok": True, "result": result})
        except HTTPException as exc:
            results.append({"ok": False, "filename": Path(file.filename or "").name, "error": exc.detail})
    successful = [item["result"] for item in results if item["ok"]]
    abnormal = sum(1 for item in successful if item["abnormal"])
    return {"results": results, "total": len(files), "processed": len(successful), "abnormal_count": abnormal}


@app.post("/feedback")
def submit_feedback(feedback: FeedbackRequest):
    if not get_record(feedback.record_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ cần phản hồi.")
    corrected = feedback.corrected_disease_code.upper() if feedback.corrected_disease_code else ""
    if feedback.doctor_status == "CORRECTED" and corrected not in DISEASES_DATA:
        raise HTTPException(status_code=422, detail="Hãy chọn một mã bệnh hợp lệ khi đính chính.")
    if feedback.doctor_status == "CONFIRMED":
        corrected = ""
    disease_name = DISEASES_DATA[corrected]["name_vi"] if corrected else ""
    save_feedback({
        "record_id": feedback.record_id,
        "doctor_status": feedback.doctor_status,
        "corrected_disease_code": corrected,
        "corrected_disease_name": disease_name,
        "doctor_notes": feedback.doctor_notes or "",
    })
    return {"status": "success", "feedback": get_feedback(feedback.record_id)}


@app.get("/export/xlsx")
def export_xlsx(
    pen_id: Optional[str] = None,
    ear_tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=503, detail="Chưa cài openpyxl. Chạy pip install -r backend/requirements.txt.")
    records = get_records(200, pen_id=pen_id, ear_tag=ear_tag, start_date=start_date, end_date=end_date)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lịch sử phân tích"
    headers = ["Mã phân tích", "Tên ảnh", "Mã tai", "Dãy chuồng", "Kết quả", "Mã bệnh", "Độ tin cậy", "Mức cảnh báo", "Ghi chú", "Thời gian"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="315B49")
    for item in records:
        sheet.append([item["id"], item["filename"], item["ear_tag"], item["pen_id"], item["disease_name"], item["disease_code"], item["confidence"], item["urgency_label"], item["notes"], item["created_at"]])
    for column in sheet.columns:
        width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 42)
        sheet.column_dimensions[column[0].column_letter].width = width
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=pigskin-history.xlsx"})


def _pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("PigSkinSans", str(path)))
            return "PigSkinSans"
    return "Helvetica"


@app.get("/export/pdf/{record_id}")
def export_record_pdf(record_id: str):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image as PDFImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise HTTPException(status_code=503, detail="Chưa cài reportlab. Chạy pip install -r backend/requirements.txt.")
    record = get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ cần xuất.")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=f"Phiếu phân tích {record_id}")
    font = _pdf_font()
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PigSkinTitle", parent=styles["Title"], fontName=font, fontSize=20, textColor=colors.HexColor("#203b30"), alignment=TA_LEFT, spaceAfter=8)
    body = ParagraphStyle("PigSkinBody", parent=styles["BodyText"], fontName=font, fontSize=10, leading=15)
    story = [Paragraph("Phiếu phân tích ảnh da heo", title), Paragraph("Bản ghi nghiên cứu · Không thay thế chẩn đoán của bác sĩ thú y", body), Spacer(1, 7 * mm)]
    rows = [
        ["Mã hồ sơ", record["id"]], ["Thời gian", record["created_at"]],
        ["Mã tai / chuồng", f"{record['ear_tag'] or '—'} / {record['pen_id'] or '—'}"],
        ["Kết quả mô hình", record["disease_name"]], ["Độ tin cậy", f"{record['confidence'] * 100:.1f}%"],
        ["Mức cảnh báo", record["urgency_label"]],
    ]
    table = Table([[Paragraph(str(a), body), Paragraph(str(b), body)] for a, b in rows], colWidths=[43 * mm, 125 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3ed")), ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#dce5dc")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.extend([table, Spacer(1, 6 * mm), Paragraph("Ghi chú", styles["Heading3"]), Paragraph(record["notes"] or "Không có ghi chú.", body), Spacer(1, 4 * mm), Paragraph("Hướng xử lý tham khảo", styles["Heading3"]), Paragraph(record["treatment_summary"] or "Theo dõi biểu hiện và liên hệ bác sĩ thú y để được đánh giá.", body)])
    image_path = BASE_DIR / record.get("image_path", "")
    if image_path.is_file():
        story.extend([Spacer(1, 6 * mm), Paragraph("Ảnh đã lưu", styles["Heading3"]), PDFImage(str(image_path), width=70 * mm, height=58 * mm, kind="proportional")])
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={record_id}.pdf"})


@app.get("/models")
def list_models():
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    models = [{"filename": path.name, "format": path.suffix.lower(), "size_bytes": path.stat().st_size, "loadable": False} for path in sorted(WEIGHTS_DIR.iterdir()) if path.is_file() and path.suffix.lower() in {".pt", ".onnx"}]
    return {"models": models, "active_model": None, "inference_ready": False, "message": "Chưa có bộ nạp mô hình trong backend."}


@app.post("/models/switch")
def switch_model(request: ModelSwitchRequest):
    candidate = Path(request.filename).name
    path = (WEIGHTS_DIR / candidate).resolve()
    if path.parent != WEIGHTS_DIR.resolve() or path.suffix.lower() not in {".pt", ".onnx"} or not path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp mô hình hợp lệ trong ml_workspace/weights.")
    raise HTTPException(status_code=409, detail="Tệp trọng số tồn tại nhưng chưa có bộ nạp suy luận để kích hoạt an toàn.")
