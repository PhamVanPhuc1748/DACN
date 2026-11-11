"""
PigSkinTech Veterinary AI Chatbot Service:
- Real Gemini REST API integration (`gemini-2.5-flash` via `GEMINI_API_KEY` in `.env`)
- Dynamic `VET_SYSTEM_PROMPT` injected with full `models/classes.json` clinical catalog
- Strict Domain Guardrail + Non-clinical playful pig query detection
- Mandatory Footer Disclaimer (`ensure_disclaimer`)
- Real-time synchronization across all Chat views (`refresh_all_chat_views`)
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Callable

import requests

from services.config_store import read_settings
from services.project_data import display_class, get_class_info, list_model_runs, load_classes_config

OFF_TOPIC_REFUSAL = (
    "Xin lỗi bạn, đây là Chatbox chuyên biệt của PigSkinTech giúp bạn tìm hiểu thêm về "
    "bệnh ngoài da ở heo và cách chăm sóc đàn heo, chứ không giải đáp các câu hỏi ngoài lề. "
    "Bạn có thắc mắc nào về tình trạng sức khỏe hay dấu hiệu trên da của heo không?"
)

NON_CLINICAL_PIG_REMINDER = (
    "Hiện tượng bạn mô tả không phải là triệu chứng bệnh lý ngoài da ở heo. "
    "Chatbox PigSkinTech chuyên hỗ trợ tư vấn các dấu hiệu tổn thương da "
    "(như nổi mẩn đỏ, mụn nước, đóng vảy, ghẻ, nấm...) và phác đồ chăm sóc. "
    "Bạn vui lòng mô tả cụ thể biểu hiện trên da của heo nhé!"
)

MANDATORY_DISCLAIMER = (
    "⚠️ Lưu ý: Câu trả lời từ Chatbox AI chỉ mang tính chất tham khảo bước đầu. "
    "Để có chẩn đoán và phác đồ điều trị chính xác nhất, bạn vui lòng gửi yêu cầu thẩm định "
    "cho Chuyên gia Thú y trên ứng dụng hoặc liên hệ bác sĩ thú y trực tiếp."
)


def format_diagnosis_context(result: dict | None) -> str:
    if not result or not result.get("label"):
        return ""
    label = str(result.get("label") or "")
    cls_info = get_class_info(label)
    name_vi = result.get("display_label") or cls_info.get("name_vi", label)
    conf_pct = f"{float(result.get('confidence') or 0.0) * 100:.1f}%"
    arch = result.get("architecture") or result.get("model_label") or result.get("model_info") or "MobileNetV2"
    ms = result.get("inference_ms", "-")
    scores = result.get("top3") or (result.get("scores") or [])[:3]
    top3_str = ", ".join(
        f"{display_class(s.get('label'))} ({float(s.get('confidence') or 0.0)*100:.1f}%)"
        for s in scores
    )
    return (
        f"- Kết quả mô hình vừa quét: {name_vi} ({label})\n"
        f"- Độ tự tin Softmax: {conf_pct} | Kiến trúc mạng: {arch} | Thời gian suy luận: {ms} ms\n"
        f"- Top-3 xác suất Softmax: {top3_str}\n"
        f"- Mức độ nguy hiểm: {cls_info.get('danger_level', 'Trung bình')}\n"
        f"- Triệu chứng điển hình: {cls_info.get('symptoms', '')}\n"
        f"- Phác đồ điều trị & Liều lượng thuốc: {cls_info.get('treatment', '')}\n"
        f"- Biện pháp cách ly & Phòng bệnh: {cls_info.get('prevention', '')}"
    )


def build_vet_system_prompt(result_context: dict | None = None) -> str:
    """
    Xây dựng VET_SYSTEM_PROMPT truyền toàn bộ danh sách bệnh lý và phác đồ thật từ
    `models/classes.json` cùng kết quả chẩn đoán hiện tại để Gemini AI trả lời chính xác.
    """
    catalog = load_classes_config()
    catalog_lines = []
    for code, info in catalog.items():
        catalog_lines.append(
            f"- Mã lớp: {code} | Tên bệnh: {info.get('name_vi', code)} | Mức độ nguy hiểm: {info.get('danger_level', 'Trung bình')}\n"
            f"  + Triệu chứng nhận diện: {info.get('symptoms', '')}\n"
            f"  + Phòng ngừa & Cách ly: {info.get('prevention', '')}\n"
            f"  + Phác đồ điều trị chuẩn: {info.get('treatment', '')}"
        )
    catalog_block = "\n".join(catalog_lines)

    prompt = (
        "Bạn là Trợ lý Bác sĩ Thú y AI chuyên biệt của ứng dụng PigSkinTech.\n\n"
        "=== CƠ SỞ DỮ LIỆU BỆNH LÝ & PHÁC ĐỒ THẬT TỪ MODELS/CLASSES.JSON ===\n"
        f"{catalog_block}\n\n"
        "=== QUY TẮC KIỂM SOÁT NỘI DUNG NGHIÊM NGẶT (STRICT DOMAIN GUARDRAIL) ===\n"
        "1. Bạn CHỈ ĐƯỢC PHÉP trả lời các câu hỏi thuộc chuyên môn của ứng dụng PigSkinTech:\n"
        "   - Các bệnh ngoài da ở heo (triệu chứng, nguyên nhân, mức độ lây lan, cách ly, vệ sinh chuồng trại, chăm sóc bước đầu, phác đồ và liều lượng thuốc tham khảo dựa trên danh mục bệnh lý ở trên).\n"
        "   - Giải thích kết quả chẩn đoán từ mô hình Deep Learning (MobileNetV2, EfficientNet-B0, độ tự tin Softmax, Top-3 xác suất, thời gian suy luận).\n"
        "   - Hướng dẫn sử dụng ứng dụng PigSkinTech (tải ảnh quét bệnh, gửi yêu cầu thẩm định cho Chuyên gia Thú y, xuất phiếu khám A4, xem lịch sử và cẩm nang bệnh lý).\n"
        "2. Nếu người dùng hỏi câu vô nghĩa hoặc đùa cợt dù có chữ 'heo'/'lợn' nhưng KHÔNG phải triệu chứng bệnh lý thật (ví dụ: 'con heo hôm nay nó nhảy cao lắm làm sao bây giờ', 'heo biết bay', 'heo hát'...), hãy trả lời ĐÚNG nguyên văn câu nhắc nhở sau:\n"
        f"\"{NON_CLINICAL_PIG_REMINDER}\"\n"
        "3. Tuyệt đối KHÔNG trả lời các câu hỏi ngoài lề, tán gẫu, thời tiết, bóng đá, thể thao, toán học, lập trình, giải trí, chính trị, nấu ăn, đời sống... Nếu câu hỏi ngoài lề, hãy trả lời ĐÚNG nguyên văn câu từ chối sau:\n"
        f"\"{OFF_TOPIC_REFUSAL}\"\n"
        "4. Trình bày câu trả lời ngắn gọn, rõ ràng, dễ hiểu bằng tiếng Việt có định dạng Markdown (dùng **in đậm** cho ý chính và danh sách gạch đầu dòng)."
    )
    ctx_str = format_diagnosis_context(result_context)
    if ctx_str:
        prompt += f"\n\n=== NGỮ CẢNH KẾT QUẢ MÔ HÌNH VỪA QUÉT ===\n{ctx_str}"
    return prompt


STRICT_DOMAIN_SYSTEM_PROMPT = build_vet_system_prompt()
VET_SYSTEM_PROMPT = STRICT_DOMAIN_SYSTEM_PROMPT

# Từ khóa chặn ngoài lề (thời tiết, bóng đá, toán học, lập trình, giải trí, tán gẫu...)
_OFF_TOPIC_PATTERNS: tuple[str, ...] = (
    "thời tiết",
    "trời có đẹp",
    "trời mưa",
    "trời nắng",
    "nhiệt độ hôm nay",
    "dự báo thời tiết",
    "bóng đá",
    "world cup",
    "ngoại hạng anh",
    "cầu thủ",
    "bàn thắng",
    "đội tuyển",
    "thể thao",
    "lập trình",
    "viết code",
    "python",
    "javascript",
    "html",
    "css",
    "c++",
    "java",
    "thuật toán",
    "toán học",
    "giải phương trình",
    "tính tích phân",
    "đạo hàm",
    "1+1",
    "2+2",
    "bằng mấy",
    "chứng khoán",
    "bitcoin",
    "crypto",
    "giá vàng",
    "tỷ giá",
    "bất động sản",
    "xổ số",
    "lô đề",
    "tử vi",
    "bói toán",
    "cung hoàng đạo",
    "phim ảnh",
    "ca sĩ",
    "bài hát",
    "nghe nhạc",
    "chơi game",
    "liên quân",
    "genshin",
    "chính trị",
    "tổng thống",
    "chiến tranh",
    "kể chuyện cười",
    "làm thơ",
    "viết văn",
    "nấu ăn",
    "công thức nấu",
    "hôm nay ăn gì",
    "mấy giờ rồi",
    "hôm nay thứ mấy",
    "bạn có người yêu chưa",
    "bạn bao nhiêu tuổi",
)

# Từ khóa hành vi đùa cợt / phi bệnh lý dù có nhắc tới chữ "heo" / "lợn"
_PLAYFUL_PIG_PATTERNS: tuple[str, ...] = (
    "nhảy cao",
    "nhảy múa",
    "biết bay",
    "biết hát",
    "hát hay",
    "biết nói",
    "đá bóng",
    "chạy đua",
    "xem tivi",
    "xem phim",
    "chơi game",
    "làm toán",
    "học bài",
    "đi học",
    "cười tươi",
    "đẹp trai",
    "xinh gái",
    "heo quay",
    "lợn quay",
    "thịt kho",
    "luộc thịt",
    "nướng thịt",
    "món ăn",
    "giá thịt heo",
    "giá hơi hôm nay",
)

# Từ khóa triệu chứng lâm sàng, bệnh da heo, điều trị, mô hình AI & ứng dụng thực sự
_CLINICAL_OR_APP_KEYWORDS: tuple[str, ...] = (
    "da",
    "ngoài da",
    "vùng da",
    "lỗ tai",
    "vành tai",
    "mõm",
    "móng",
    "bụng",
    "lưng",
    "cổ",
    "chân",
    "chuồng",
    "trang trại",
    "trại",
    "chăn nuôi",
    "thú y",
    "bác sĩ",
    "bệnh",
    "triệu chứng",
    "dấu hiệu",
    "biểu hiện",
    "nguyên nhân",
    "đóng dấu",
    "erysipelas",
    "ghẻ",
    "mange",
    "sarcoptes",
    "viêm",
    "tiết dịch",
    "greasy",
    "staphylococcus",
    "nấm",
    "hắc lào",
    "ringworm",
    "trichophyton",
    "vảy phấn",
    "pityriasis",
    "đậu",
    "swinepox",
    "lở mồm",
    "long móng",
    "fmd",
    "cháy nắng",
    "sunburn",
    "nốt",
    "mẩn",
    "mảng",
    "đỏ",
    "hình thoi",
    "vảy",
    "bong",
    "mụn",
    "loét",
    "rỉ dịch",
    "dịch nhờn",
    "ngứa",
    "gãi",
    "cọ",
    "rụng lông",
    "sốt",
    "bỏ ăn",
    "kém ăn",
    "ủ rũ",
    "tím",
    "xuất huyết",
    "nhiễm trùng",
    "vi khuẩn",
    "ký sinh trùng",
    "virus",
    "khỏe",
    "healthy",
    "điều trị",
    "chữa",
    "phác đồ",
    "thuốc",
    "kháng sinh",
    "liều",
    "tiêm",
    "bôi",
    "xịt",
    "tắm",
    "penicillin",
    "amoxicillin",
    "ceftiofur",
    "ivermectin",
    "doramectin",
    "amitraz",
    "iodine",
    "povidone",
    "ketoconazole",
    "griseofulvin",
    "kẽm",
    "vitamin",
    "điện giải",
    "hạ sốt",
    "kháng viêm",
    "cách ly",
    "lây",
    "nguy hiểm",
    "sát trùng",
    "khử trùng",
    "vệ sinh",
    "vôi bột",
    "an toàn sinh học",
    "phòng bệnh",
    "phòng ngừa",
    "vắc xin",
    "vaccine",
    "chăm sóc",
    "xử lý",
    "kết quả",
    "chẩn đoán",
    "quét",
    "phân tích",
    "mô hình",
    "model",
    "deep learning",
    "mobilenet",
    "mobilenetv2",
    "efficientnet",
    "efficientnet-b0",
    "softmax",
    "xác suất",
    "độ tự tin",
    "độ tin cậy",
    "confidence",
    "top-3",
    "top 3",
    "tensor",
    "suy luận",
    "inference",
    "kiến trúc",
    "ca khám",
    "ca bệnh",
    "pigskintech",
    "ứng dụng",
    "cách dùng",
    "hướng dẫn",
    "tải ảnh",
    "chọn ảnh",
    "upload",
    "thẩm định",
    "chuyên gia",
    "gửi yêu cầu",
    "phiếu khám",
    "in phiếu",
    "xuất phiếu",
    "báo cáo a4",
    "lịch sử khám",
    "cẩm nang",
)

# Danh sách từ khóa tổng hợp để nhận diện câu hỏi có liên quan tới lĩnh vực
_DOMAIN_KEYWORDS: tuple[str, ...] = ("heo", "lợn", "pig", "swine") + _CLINICAL_OR_APP_KEYWORDS


def _normalize_text(text: str) -> str:
    norm = unicodedata.normalize("NFC", (text or "").strip().lower())
    return re.sub(r"\s+", " ", norm)


def ensure_disclaimer(reply: str) -> str:
    """
    Hàm hậu xử lý bắt buộc gắn dòng cảnh báo tham khảo ở cuối 100% câu trả lời của Chatbox
    trước khi hiển thị lên UI và trước khi lưu vào bảng ChatMessages trong SQL Database.
    """
    cleaned = unicodedata.normalize("NFC", (reply or "").strip())
    if not cleaned:
        cleaned = OFF_TOPIC_REFUSAL

    disclaimer_norm = unicodedata.normalize("NFC", MANDATORY_DISCLAIMER)
    if disclaimer_norm in cleaned:
        cleaned = cleaned.replace(disclaimer_norm, "").strip()

    cleaned = re.sub(
        r"(?:\n|\r|\s)*⚠️\s*Lưu ý:\s*Câu trả lời từ Chatbox AI chỉ mang tính chất tham khảo bước đầu.*$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    return f"{cleaned}\n\n{MANDATORY_DISCLAIMER}"


def is_non_clinical_pig_question(question: str) -> bool:
    """
    Phát hiện câu hỏi có nhắc đến 'heo'/'lợn' nhưng mang tính chất đùa cợt, vô nghĩa,
    không phải triệu chứng bệnh lý ngoài da thật (VD: 'con heo hôm nay nó nhảy cao lắm làm sao bây giờ').
    """
    q = _normalize_text(question)
    if not q:
        return False

    mentions_pig = any(w in q for w in ("heo", "lợn", "pig", "swine"))
    if not mentions_pig:
        return False

    has_clinical_kw = any(kw in q for kw in _CLINICAL_OR_APP_KEYWORDS)
    if any(pat in q for pat in _PLAYFUL_PIG_PATTERNS) and not has_clinical_kw:
        return True

    # Nếu câu hỏi có chữ 'heo'/'lợn' nhưng hoàn toàn không chứa bất kỳ từ khóa da liễu, triệu chứng,
    # chăm sóc, chuồng trại, mô hình AI hay ứng dụng nào -> Nhắc nhở mô tả triệu chứng trên da
    if not has_clinical_kw:
        return True

    return False


def is_in_domain(question: str, result_context: dict | None = None) -> bool:
    """
    Kiểm tra nghiêm ngặt câu hỏi của người dùng có thuộc phạm vi chuyên môn của PigSkinTech hay không.
    """
    q = _normalize_text(question)
    if not q:
        return False

    if re.search(r"\b\d+\s*[\+\-\*\/\^]\s*\d+", q) and not any(k in q for k in ("mg/kg", "ml/", "liều", "heo", "lợn", "ngày", "kg")):
        return False

    has_domain_kw = any(kw in q for kw in _DOMAIN_KEYWORDS)
    if not has_domain_kw:
        catalog = load_classes_config()
        for code, info in catalog.items():
            name_vi = _normalize_text(str(info.get("name_vi", "")))
            if code.lower() in q or (name_vi and name_vi in q):
                has_domain_kw = True
                break

    has_off_topic = any(pat in q for pat in _OFF_TOPIC_PATTERNS)
    if has_off_topic:
        if not any(w in q for w in ("heo", "lợn", "chuồng", "da heo", "da lợn", "pigskintech")):
            return False

    return has_domain_kw


def build_refusal_response() -> str:
    """Trả về thông điệp từ chối lịch sự chuẩn của PigSkinTech kèm cảnh báo bắt buộc ở cuối."""
    return ensure_disclaimer(OFF_TOPIC_REFUSAL)


def build_non_clinical_pig_response() -> str:
    """Trả về thông điệp nhắc nhở khi người dùng mô tả hiện tượng phi bệnh lý ở heo."""
    return ensure_disclaimer(NON_CLINICAL_PIG_REMINDER)


def _call_gemini_rest_api(
    api_key: str,
    model_name: str,
    system_prompt: str,
    question: str,
    history: list[dict],
) -> tuple[str | None, str]:
    """
    Gọi trực tiếp REST API Gemini (`https://generativelanguage.googleapis.com/v1beta/models/...:generateContent`)
    bằng `requests` để không bị lỗi phụ thuộc thư viện.
    """
    candidate_models = [model_name or "gemini-2.5-flash"]
    for fallback_m in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    contents: list[dict] = []
    for item in history[-8:]:
        role_raw = item.get("role", "")
        text_raw = (item.get("content") or "").strip()
        if not text_raw or role_raw not in ("user", "assistant"):
            continue
        gemini_role = "user" if role_raw == "user" else "model"
        contents.append({"role": gemini_role, "parts": [{"text": text_raw}]})
    contents.append({"role": "user", "parts": [{"text": question}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 900,
        },
    }

    for m_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=25,
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates") or []
                if candidates:
                    parts = ((candidates[0].get("content") or {}).get("parts")) or []
                    reply_txt = "".join(str(p.get("text") or "") for p in parts).strip()
                    if reply_txt:
                        return reply_txt, m_name
        except Exception:
            continue
    return None, model_name


def _clinical_domain_answer(question: str, result: dict | None) -> tuple[str, str]:
    """
    Trả lời chuyên sâu dựa trên `models/classes.json` và kết quả mô hình vừa quét.
    """
    q_low = _normalize_text(question)
    catalog = load_classes_config()

    asks_app_guide = any(
        k in q_low
        for k in (
            "hướng dẫn sử dụng",
            "hướng dẫn dùng",
            "cách dùng",
            "cách sử dụng",
            "tải ảnh",
            "xuất phiếu",
            "in phiếu",
            "báo cáo a4",
            "gửi yêu cầu thẩm định",
        )
    )
    if asks_app_guide:
        reply = (
            "📱 **Hướng dẫn sử dụng ứng dụng PigSkinTech:**\n\n"
            "1. **Chẩn đoán bệnh từ ảnh chụp:** Mở tab **Chẩn đoán bệnh**, chọn mô hình Deep Learning (`MobileNetV2` hoặc `EfficientNet-B0`), bấm **Chọn tập tin ảnh** để tải ảnh vùng da heo nghi ngờ và xem kết quả phân tích Softmax tức thì.\n"
            "2. **Hỏi đáp phác đồ cùng Trợ lý AI:** Sau khi quét ảnh, bấm nút **\"💬 Hỏi AI Thú y\"** ngay cạnh kết quả hoặc mở tab **Trợ lý AI Thú y (Chatbot)** để hỏi chi tiết về triệu chứng, cách ly và chăm sóc bước đầu.\n"
            "3. **Gửi thẩm định Chuyên gia Thú y:** Bấm nút **\"Gửi Chuyên gia\"** trên thẻ kết quả để Bác sĩ Thú y kiểm tra chéo, gán nhãn chuẩn và đưa ra khuyến nghị chuyên sâu.\n"
            "4. **Xuất Phiếu khám A4 & Tra cứu:** Bấm **\"In Phiếu khám\"** để xuất báo cáo 1 trang A4 hoặc vào tab **Cẩm nang bệnh lý** / **Lịch sử khám** để tra cứu hồ sơ."
        )
        return ensure_disclaimer(reply), "PigSkinTech Clinical AI"

    asks_model_explain = any(
        k in q_low
        for k in ("mobilenet", "efficientnet", "deep learning", "softmax", "top-3", "top 3", "tensor", "kiến trúc mạng", "mô hình hoạt động")
    )
    if asks_model_explain:
        models_info = list_model_runs()
        models_txt = "\n".join(
            f"• **{m.get('model_label', m.get('model'))}** (`{m['run_name']}`): Độ chính xác tập kiểm thử (Test Accuracy) đạt **{float(m.get('test_acc') or 0.0)*100:.2f}%**."
            for m in models_info
        )
        scan_explain = ""
        if result and result.get("label"):
            lbl_vi = result.get("display_label") or display_class(result.get("label"))
            conf_pct = f"{float(result.get('confidence') or 0.0)*100:.1f}%"
            arch = result.get("architecture") or result.get("model_label") or "MobileNetV2"
            ms = result.get("inference_ms", "-")
            scores = result.get("top3") or (result.get("scores") or [])[:3]
            top3_str = " | ".join(
                f"{display_class(s.get('label'))}: {float(s.get('confidence') or 0.0)*100:.1f}%"
                for s in scores
            )
            scan_explain = (
                f"\n\n🔬 **Giải thích ca quét hiện tại của bạn:**\n"
                f"• Mạng nơ-ron **{arch}** đã trích xuất đặc trưng bề mặt tổn thương da và tính hàm **Softmax** trên các lớp bệnh lý.\n"
                f"• Nhãn có xác suất cao nhất là **{lbl_vi}** với độ tự tin **{conf_pct}** (thời gian suy luận **{ms} ms**).\n"
                f"• Phân bố **Top-3 Softmax**: {top3_str}."
            )
        reply = (
            "🧠 **Giải thích cơ chế chẩn đoán Deep Learning trên PigSkinTech:**\n\n"
            "Hệ thống sử dụng mạng nơ-ron tích chập (CNN) huấn luyện trên tập ảnh lâm sàng da heo chuẩn hóa (`224×224`, chuẩn hóa ImageNet):\n"
            f"{models_txt}\n"
            "• **Độ tự tin Softmax & Top-3:** Biểu thị phân phối xác suất đầu ra của tensor mô hình. Khi độ tự tin dưới 75% hoặc 2 lớp dẫn đầu có xác suất gần nhau, bạn nên chụp thêm góc ảnh rõ nét hơn và gửi Chuyên gia Thú y thẩm định."
            f"{scan_explain}"
        )
        return ensure_disclaimer(reply), "PigSkinTech Clinical AI"

    matched_code = None
    for code, info in catalog.items():
        name_vi = _normalize_text(str(info.get("name_vi", "")))
        if code.lower() in q_low or (name_vi and name_vi in q_low):
            matched_code = code
            break

    if matched_code is None:
        keyword_map = {
            "đóng dấu": "Infected_Bacterial_Erysipelas",
            "hình thoi": "Infected_Bacterial_Erysipelas",
            "erysipelas": "Infected_Bacterial_Erysipelas",
            "ghẻ": "Infected_Parasitic_Mange",
            "ngứa": "Infected_Parasitic_Mange",
            "cọ xát": "Infected_Parasitic_Mange",
            "mange": "Infected_Parasitic_Mange",
            "tiết dịch": "Infected_Bacterial_Greasy_Pig_Disease",
            "dịch nhờn": "Infected_Bacterial_Greasy_Pig_Disease",
            "greasy": "Infected_Bacterial_Greasy_Pig_Disease",
            "nấm": "Infected_Fungal_Ringworm",
            "hắc lào": "Infected_Fungal_Ringworm",
            "ringworm": "Infected_Fungal_Ringworm",
            "vảy phấn": "Infected_Fungal_Pityriasis_Rosea",
            "pityriasis": "Infected_Fungal_Pityriasis_Rosea",
            "đậu": "Infected_Viral_Swinepox",
            "swinepox": "Infected_Viral_Swinepox",
            "lở mồm": "Infected_Viral_Foot_and_Mouth_Disease",
            "long móng": "Infected_Viral_Foot_and_Mouth_Disease",
            "cháy nắng": "Infected_Environmental_Sunburn",
            "sunburn": "Infected_Environmental_Sunburn",
            "môi trường": "Infected_Environmental_Dermatitis",
            "khỏe": "Healthy",
        }
        for kw, code in keyword_map.items():
            if kw in q_low and code in catalog:
                matched_code = code
                break

    if matched_code is None and result and result.get("label"):
        matched_code = str(result.get("label"))

    if matched_code:
        info = get_class_info(matched_code)
        name_vi = info.get("name_vi", matched_code)
        header_ctx = ""
        if result and result.get("label") == matched_code:
            conf_pct = f"{float(result.get('confidence') or 0.0)*100:.1f}%"
            arch = result.get("architecture") or result.get("model_label") or "MobileNetV2"
            ms = result.get("inference_ms", "-")
            scores = result.get("top3") or (result.get("scores") or [])[:3]
            top3_txt = " | ".join(
                f"{display_class(s.get('label'))}: {float(s.get('confidence') or 0.0)*100:.1f}%"
                for s in scores
            )
            header_ctx = (
                f"📊 **Kết quả mô hình vừa quét:** Kiến trúc **{arch}** chẩn đoán **{name_vi}** "
                f"với độ tự tin Softmax **{conf_pct}** ({ms} ms).\n"
                f"• Top-3 Softmax: {top3_txt}\n\n"
            )

        asks_drug = any(k in q_low for k in ("thuốc", "liều", "tiêm", "kháng sinh", "điều trị", "chữa", "phác đồ", "bôi", "chăm sóc"))
        asks_iso = any(k in q_low for k in ("cách ly", "khử trùng", "sát trùng", "lây", "chuồng", "vệ sinh", "phòng"))
        asks_symp = any(k in q_low for k in ("triệu chứng", "dấu hiệu", "nhận biết", "biểu hiện", "nguyên nhân", "sốt", "ngứa"))

        body_parts = [f"🩺 **Tư vấn Thú y AI — {name_vi} ({matched_code})**\n\n", header_ctx]
        if asks_drug and not (asks_iso or asks_symp):
            body_parts.append(
                f"💊 **Chăm sóc bước đầu & Phác đồ điều trị tham khảo:**\n• {info.get('treatment', '')}\n\n"
                f"🛡️ **An toàn sinh học & Vệ sinh chuồng trại:**\n• {info.get('prevention', '')}"
            )
        elif asks_iso and not (asks_drug or asks_symp):
            body_parts.append(
                f"🚧 **Biện pháp Cách ly & Vệ sinh chuồng trại:**\n• {info.get('prevention', '')}\n\n"
                f"⚠️ **Mức độ cảnh báo lây lan:** {info.get('danger_level', 'Trung bình')}"
            )
        elif asks_symp and not (asks_drug or asks_iso):
            body_parts.append(
                f"🔍 **Triệu chứng lâm sàng & Nguyên nhân đặc trưng:**\n• {info.get('symptoms', '')}\n\n"
                f"⚠️ **Mức độ nguy hiểm:** {info.get('danger_level', 'Trung bình')}"
            )
        else:
            body_parts.append(
                f"🔍 **1. Triệu chứng nhận biết (Mức độ: {info.get('danger_level', 'Trung bình')}):**\n"
                f"• {info.get('symptoms', '')}\n\n"
                f"💊 **2. Chăm sóc bước đầu & Phác đồ tham khảo:**\n"
                f"• {info.get('treatment', '')}\n\n"
                f"🚧 **3. Cách ly & Vệ sinh chuồng trại:**\n"
                f"• {info.get('prevention', '')}"
            )
        return ensure_disclaimer("".join(body_parts)), "PigSkinTech Clinical AI"

    names_str = ", ".join(f"**{v.get('name_vi', k)}**" for k, v in catalog.items())
    general_reply = (
        "🩺 **Hướng dẫn kiểm tra & chăm sóc bước đầu bệnh ngoài da ở heo:**\n\n"
        f"• Hệ thống PigSkinTech hiện hỗ trợ nhận diện chuyên sâu các nhóm: {names_str}.\n"
        "• **Nguyên tắc xử lý bước đầu tại trại:**\n"
        "  1. **Cách ly:** Tách riêng cá thể heo có biểu hiện nổi mẩn đỏ, đóng vảy, mụn nước hoặc ngứa gãi sang ô chuồng cách ly khô ráo, thoáng khí.\n"
        "  2. **Kiểm tra lâm sàng:** Đo thân nhiệt heo (sốt cao > 40.5°C thường gợi ý nhóm nhiễm khuẩn cấp như **Đóng dấu lợn**; không sốt nhưng ngứa dữ dội thường gợi ý **Ghẻ Sarcoptes** hoặc **Nấm da**).\n"
        "  3. **Sát trùng & Chẩn đoán AI:** Phun sát trùng chuồng nuôi bằng dung dịch Iodine hoặc vôi bột và tải ảnh vùng da tổn thương lên tab **Chẩn đoán bệnh** để mô hình Deep Learning phân tích chi tiết."
    )
    return ensure_disclaimer(general_reply), "PigSkinTech Clinical AI"


def ask_vet_ai(question: str, history: list[dict], result_context: dict | None = None) -> tuple[str, str]:
    """
    Xử lý câu hỏi người dùng với:
    1) Kiểm tra câu đùa cợt/phi bệnh lý về heo -> Nhắc nhở mô tả biểu hiện trên da heo
    2) Kiểm soát phạm vi chuyên môn (Strict Domain Guardrail) -> Từ chối câu hỏi ngoài lề
    3) Gọi trực tiếp Gemini REST API (`gemini-2.5-flash`) với `VET_SYSTEM_PROMPT` chứa toàn bộ `models/classes.json`
    4) Bắt buộc hậu xử lý `ensure_disclaimer(reply)` ở cuối 100% câu trả lời.
    """
    # 1. Phát hiện câu hỏi đùa cợt / phi bệnh lý dù có chữ "heo" (VD: "con heo hôm nay nó nhảy cao lắm làm sao bây giờ")
    if is_non_clinical_pig_question(question):
        return build_non_clinical_pig_response(), "PigSkinTech Clinical Guardrail"

    # 2. Kiểm soát phạm vi câu hỏi ngoài lề (Strict Domain Restriction)
    if not is_in_domain(question, result_context):
        return build_refusal_response(), "PigSkinTech Domain Guardrail"

    cfg = read_settings()
    vet_sys_prompt = build_vet_system_prompt(result_context)

    # 3. Ưu tiên gọi Gemini REST API thực tế nếu có GEMINI_API_KEY trong .env
    gemini_key = (
        cfg.get("GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or (cfg.get("AI_API_KEY") if str(cfg.get("AI_API_KEY") or "").startswith("AIza") else "")
        or ""
    ).strip()
    gemini_model = (cfg.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()

    if gemini_key:
        gem_reply, used_gem_model = _call_gemini_rest_api(
            api_key=gemini_key,
            model_name=gemini_model,
            system_prompt=vet_sys_prompt,
            question=question,
            history=history,
        )
        if gem_reply:
            return ensure_disclaimer(gem_reply), used_gem_model

    # 4. Gọi OpenAI-compatible / Local LLM nếu có cấu hình
    ai_key = (cfg.get("AI_API_KEY") or "").strip()
    ai_base = (cfg.get("AI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
    ai_model = (cfg.get("AI_MODEL") or "gpt-4o-mini").strip()
    is_local_llm = any(h in ai_base for h in ("localhost", "127.0.0.1", "11434"))

    if (ai_key and not ai_key.startswith("AIza")) or is_local_llm:
        endpoint = ai_base if ai_base.endswith("/chat/completions") else f"{ai_base}/chat/completions"
        messages = [{"role": "system", "content": vet_sys_prompt}]
        for item in history[-8:]:
            if item.get("role") in ("user", "assistant") and item.get("content"):
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": question})
        headers = {"Content-Type": "application/json"}
        if ai_key:
            headers["Authorization"] = f"Bearer {ai_key}"
        try:
            resp = requests.post(
                endpoint,
                json={"model": ai_model, "messages": messages, "temperature": 0.25},
                headers=headers,
                timeout=25,
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if choices:
                    reply = (choices[0].get("message") or {}).get("content") or ""
                    if reply.strip():
                        return ensure_disclaimer(reply.strip()), ai_model
        except Exception:
            pass

    # 5. Cơ sở tri thức lâm sàng nội bộ + kết quả tensor thực tế từ models/classes.json
    return _clinical_domain_answer(question, result_context)


# --- Đồng bộ hóa tức thì giữa Tab Chatbox chính và Popup Chat góc phải ---

_GLOBAL_CHAT_REFRESHERS: list[Callable[[], None]] = []


def register_chat_refresher(page: object, refresh_fn: Callable[[], None]) -> None:
    """Đăng ký hàm làm mới giao diện khung chat (Tab chính & Popup nổi) để đồng bộ 100%."""
    if refresh_fn not in _GLOBAL_CHAT_REFRESHERS:
        _GLOBAL_CHAT_REFRESHERS.append(refresh_fn)
    if page is not None and hasattr(page, "data"):
        if not isinstance(getattr(page, "data", None), dict):
            page.data = {}
        lst = page.data.setdefault("chat_view_refreshers", [])
        if refresh_fn not in lst:
            lst.append(refresh_fn)


def clear_chat_refreshers(page: object = None) -> None:
    _GLOBAL_CHAT_REFRESHERS.clear()
    if page is not None and isinstance(getattr(page, "data", None), dict):
        page.data["chat_view_refreshers"] = []


def refresh_all_chat_views(page: object = None) -> None:
    """
    Làm mới tức thì toàn bộ các khung Chat đang hiển thị (cả Tab 'Trợ lý AI Thú y' và Popup Chat góc phải)
    từ bảng ChatMessages trong SQL Database.
    """
    callbacks: list[Callable[[], None]] = []
    if page is not None and isinstance(getattr(page, "data", None), dict):
        for fn in page.data.get("chat_view_refreshers", []):
            if fn not in callbacks:
                callbacks.append(fn)
    for fn in list(_GLOBAL_CHAT_REFRESHERS):
        if fn not in callbacks:
            callbacks.append(fn)

    for fn in callbacks:
        try:
            fn()
        except Exception:
            pass
    if page is not None and hasattr(page, "update"):
        try:
            page.update()
        except Exception:
            pass
