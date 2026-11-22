"""Automated Full-System QA/QC Audit Suite for PigSkinTech."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings

import flet as ft
import numpy as np
from PIL import Image, ImageDraw

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from services import auth_service, chatbot_service, inference, inference_service, project_data, store
from services.clinical_widgets import (
    build_dual_benchmark_card,
    build_model_evaluation_lab_card,
    build_smart_dosage_calculator,
    calculate_smart_dosage,
    open_disease_editor_modal,
    render_learning_curves_png,
)


class _DummySession(dict):
    def set(self, k, v):
        self[k] = v

    def get(self, k, d=None):
        return super().get(k, d)

    def contains_key(self, k):
        return k in self

    def remove(self, k):
        self.pop(k, None)


class _DummyPage:
    def __init__(self):
        self.session = _DummySession()
        self.theme_mode = ft.ThemeMode.LIGHT
        self.bgcolor = "#F8FAFC"
        self.controls = []
        self.overlay = []
        self.services = []
        self.data = {}
        self.route = "/user"
        self.width = 1440
        self.height = 900
        self.appbar = None
        self.dialog = None

    def update(self):
        pass

    def go(self, route):
        self.route = route

    def open(self, dlg):
        self.dialog = dlg

    def close(self, dlg):
        self.dialog = None


class PigSkinQAAuditTests(unittest.TestCase):
    # --- 1. Non-Pig / OOD Gatekeeper & Real Pig Inference ---

    def test_01_real_pig_gallery_images_valid(self):
        """All 5 real pig images (including close-up skin lesion) must pass with is_valid_pig=True."""
        samples = [s for s in store.get_sample_gallery() if s.get("exists")]
        self.assertGreaterEqual(len(samples), 5)
        for sample in samples:
            res = inference.predict(sample["path"])
            self.assertTrue(res.get("is_valid_pig"), f"False reject on real pig image {sample['filename']}: {res}")
            self.assertEqual(res.get("mode"), "ai")
            self.assertTrue(res.get("ok"))
            self.assertIsNotNone(res.get("label"))
            self.assertGreaterEqual(float(res.get("confidence") or 0.0), 0.45)

    def test_02_non_pig_synthetic_images_blocked_and_not_saved(self):
        """Solid color, random noise, screenshot-like, and checkerboard images must return is_valid_pig=False."""
        rng = np.random.default_rng(42)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            p_solid = td_path / "solid.jpg"
            Image.new("RGB", (300, 300), (30, 120, 220)).save(p_solid)

            p_noise = td_path / "noise.jpg"
            Image.fromarray(rng.integers(0, 255, (300, 300, 3), dtype=np.uint8)).save(p_noise)

            p_scr = td_path / "screenshot.png"
            im_scr = Image.new("RGB", (600, 400), (255, 255, 255))
            dr = ImageDraw.Draw(im_scr)
            dr.rectangle([0, 0, 600, 40], fill=(30, 41, 59))
            for y in range(60, 360, 24):
                dr.rectangle([30, y, 520, y + 10], fill=(50, 50, 60))
            im_scr.save(p_scr)

            p_chk = td_path / "checker.png"
            arr = np.zeros((256, 256, 3), dtype=np.uint8)
            for r in range(8):
                for c in range(8):
                    if (r + c) % 2 == 0:
                        arr[r * 32 : (r + 1) * 32, c * 32 : (c + 1) * 32] = 255
            Image.fromarray(arr).save(p_chk)

            for bad_path in (p_solid, p_noise, p_scr, p_chk):
                res = inference.predict(bad_path)
                self.assertFalse(res.get("is_valid_pig"), f"Non-pig image was NOT blocked: {bad_path.name} -> {res}")
                self.assertEqual(res.get("mode"), "invalid_image")
                self.assertIsNone(res.get("label"))
                # Persistence layer must also refuse saving invalid_pig results
                with self.assertRaises(ValueError):
                    store.save(res["info"], res, case={"animal_id": "BAD-01"}, source_image=bad_path)

    # --- 2. Image Formats, Unicode Paths, Corrupted & Oversized Files ---

    def test_03_rgba_grayscale_unicode_and_corrupted_files(self):
        """RGBA 4-channel, Grayscale 1-channel, Vietnamese Unicode paths must work; corrupted/fake/oversized files must fail gracefully."""
        sample_pig = Path(store.get_sample_gallery()[0]["path"])
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            # RGBA 4-channel PNG with Vietnamese accents & spaces in path
            rgba_path = td_path / "Ảnh heo đóng dấu (RGBA 4 kênh).png"
            with Image.open(sample_pig) as im:
                im.convert("RGBA").save(rgba_path, format="PNG")
            res_rgba = inference.predict(rgba_path)
            self.assertTrue(res_rgba.get("is_valid_pig"))
            self.assertEqual(res_rgba.get("mode"), "ai")

            # Grayscale 1-channel image
            gray_path = td_path / "heo_xam.png"
            with Image.open(sample_pig) as im:
                im.convert("L").save(gray_path, format="PNG")
            info_gray = inference.inspect_image(gray_path)
            self.assertGreater(info_gray["width"], 0)

            # Fake .jpg (plain text renamed to .jpg)
            fake_jpg = td_path / "fake.jpg"
            fake_jpg.write_text("This is plain text, not a JPEG!", encoding="utf-8")
            with self.assertRaises(ValueError):
                inference.inspect_image(fake_jpg)

            # Corrupted/truncated JPEG bytes
            corrupt_jpg = td_path / "corrupt.jpg"
            raw_bytes = sample_pig.read_bytes()
            corrupt_jpg.write_bytes(raw_bytes[: max(64, len(raw_bytes) // 10)])
            with self.assertRaises(ValueError):
                inference.inspect_image(corrupt_jpg)

            # Oversized (> 15 MB)
            big_jpg = td_path / "oversized.jpg"
            big_jpg.write_bytes(b"\xff\xd8\xff" + b"\x00" * (inference.MAX_BYTES + 1024))
            with self.assertRaises(ValueError):
                inference.inspect_image(big_jpg)

    # --- 3. SQL Safety (Injection / Quotes / None fields / 2-way DiseaseCatalog / Auth Validation) ---

    def test_04_sql_injection_quotes_none_and_bidirectional_catalog(self):
        """SQL queries must safely handle quotes, SQLi payloads, None fields, unique case_id, and DiseaseCatalog sync."""
        sample_pig = Path(store.get_sample_gallery()[0]["path"])
        orig_db = store.DB
        orig_img_dir = store.IMAGE_DIR
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            store.DB = td_path / "test_qa.db"
            store.IMAGE_DIR = td_path / "imgs"
            store._SCHEMA_INITIALIZED_KEY = ""
            try:
                with patch.object(store, "read_settings", return_value={"DATABASE_ENGINE": "sqlite", "DB_NAME": "TestDB"}):
                    store.initialize(force=True)

                    info = inference.inspect_image(sample_pig)
                    fake_valid_res = {
                        "mode": "ai",
                        "is_valid_pig": True,
                        "label": "Healthy",
                        "display_label": "Da khỏe mạnh",
                        "confidence": 0.91,
                        "scores": [{"label": "Healthy", "confidence": 0.91}],
                        "model_info": "MobileNetV2 | test",
                        "inference_ms": 12.5,
                    }
                    sqli_payload = "O'Brien'; DROP TABLE inspections; --"
                    rid1 = store.save(
                        info,
                        fake_valid_res,
                        case={
                            "animal_id": None,  # Must not crash with AttributeError
                            "farm_name": sqli_payload,
                            "symptoms": "Heo sốt cao '41°C' & bỏ ăn",
                            "user_email": "nongdan.pigskin@gmail.com",
                            "user_name": "Chủ trại O'Brien",
                        },
                        source_image=sample_pig,
                    )
                    self.assertGreater(rid1, 0)
                    recs = store.recent("O'Brien")
                    self.assertEqual(len(recs), 1)
                    self.assertEqual(recs[0]["farm_name"], sqli_payload)
                    self.assertEqual(recs[0]["case_id"], f"PS-{rid1:06d}")

                    # Delete record 1 and insert record 2 -> case_id must stay valid and unique
                    store.delete(rid1)
                    rid2 = store.save(info, fake_valid_res, case={"farm_name": "Trại số 2"}, source_image=sample_pig)
                    recs2 = store.recent("")
                    self.assertEqual(len(recs2), 1)
                    self.assertEqual(recs2[0]["case_id"], f"PS-{rid2:06d}")

                    # Bidirectional DiseaseCatalog sync
                    sql_cat = store.load_disease_catalog_from_sql()
                    self.assertIn("Healthy", sql_cat)
                    self.assertIn("Infected_Bacterial_Erysipelas", sql_cat)

                    # Account validation: bad email, short password, duplicate email
                    with self.assertRaises(ValueError):
                        store.create_user_account("bad-email", "Test", password="123456")
                    with self.assertRaises(ValueError):
                        store.create_user_account("valid@farm.vn", "Test", password="123")
                    u = store.create_user_account("valid@farm.vn", "Test User", role="user", password="password123")
                    self.assertEqual(u["email"], "valid@farm.vn")
                    with self.assertRaises(ValueError):
                        store.create_user_account("valid@farm.vn", "Dup User", password="password123")
            finally:
                with store._SHARED_CONN_LOCK:
                    if store._SHARED_RAW_CONN is not None:
                        try:
                            store._SHARED_RAW_CONN.close()
                        except Exception:
                            pass
                        store._SHARED_RAW_CONN = None
                        store._SHARED_ENGINE_TYPE = None
                        store._SHARED_CONN_STR = ""
                        store._SCHEMA_INITIALIZED_KEY = ""
                store.DB = orig_db
                store.IMAGE_DIR = orig_img_dir

    # --- 4. Chatbot Domain Guardrail & API Failure Resilience ---

    def test_05_chatbot_guardrail_and_api_fallback(self):
        """Off-topic queries (including substring traps like 'data'/'today') must be refused; 429/timeout must fallback safely."""
        for off_q in (
            "Viết code Python phân tích data hôm nay",
            "1+1 bằng mấy?",
            "Dự báo thời tiết today thế nào?",
        ):
            self.assertFalse(chatbot_service.is_in_domain(off_q), f"Should reject off-topic: {off_q}")
            reply, _ = chatbot_service.ask_vet_ai(off_q, [], None)
            self.assertIn(chatbot_service.OFF_TOPIC_REFUSAL, reply)
            self.assertIn(chatbot_service.MANDATORY_DISCLAIMER, reply)

        # Friendly social greetings & thanks must be welcomed instead of refused
        for greet_q in ("xin chào", "hello", "hi", "chào bạn"):
            self.assertTrue(chatbot_service.is_in_domain(greet_q), f"Greeting must be allowed: {greet_q}")
            reply_g, _ = chatbot_service.ask_vet_ai(greet_q, [], None)
            self.assertNotIn(chatbot_service.OFF_TOPIC_REFUSAL, reply_g)
            self.assertIn("PigSkinTech", reply_g)
            self.assertIn(chatbot_service.MANDATORY_DISCLAIMER, reply_g)

        reply_thx, _ = chatbot_service.ask_vet_ai("cảm ơn bạn nhiều", [], None)
        self.assertNotIn(chatbot_service.OFF_TOPIC_REFUSAL, reply_thx)
        self.assertIn(chatbot_service.MANDATORY_DISCLAIMER, reply_thx)

        # Playful non-clinical pig question
        reply_playful, _ = chatbot_service.ask_vet_ai("con heo hôm nay biết bay làm sao?", [], None)
        self.assertIn(chatbot_service.NON_CLINICAL_PIG_REMINDER, reply_playful)

        # Simulate Gemini 429 Too Many Requests -> must fallback cleanly without raising
        class _Resp429:
            status_code = 429

        with patch.object(chatbot_service, "read_settings", return_value={"GEMINI_API_KEY": "AIzaFakeKey123", "GEMINI_MODEL": "gemini-2.5-flash"}):
            with patch.object(chatbot_service.requests, "post", return_value=_Resp429()):
                reply_ok, model_used = chatbot_service.ask_vet_ai("Triệu chứng bệnh đóng dấu lợn là gì?", [], None)
                self.assertIn("đóng dấu", reply_ok.lower())
                self.assertIn(chatbot_service.MANDATORY_DISCLAIMER, reply_ok)
                self.assertTrue(model_used)

    # --- 5. Auth Logout Cleanup, Flet Modal / Deprecations & Model Cache Eviction ---

    def test_06_logout_cleanup_modal_and_model_cache(self):
        """Logout clears page.data & chat refreshers; Disease modal builds without TypeError/warnings; model cache evicts old weights."""
        page = _DummyPage()
        page.session.set("current_user", {"user_id": 1, "role": "user"})
        page.data["active_scan_result"] = {"label": "Healthy"}
        chatbot_service.register_chat_refresher(page, lambda: None)

        auth_service.logout_user(page)
        self.assertIsNone(page.session.get("current_user"))
        self.assertEqual(page.data, {})
        self.assertEqual(len(chatbot_service._GLOBAL_CHAT_REFRESHERS), 0)

        # Disease editor modal must open without TypeError or DeprecationWarning
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            dlg = open_disease_editor_modal(page, {"code": "Healthy", "name_vi": "Da khỏe mạnh", "danger_level": "An toàn"})
            self.assertIsInstance(dlg, ft.AlertDialog)
            dep_warnings = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
            self.assertEqual(dep_warnings, [], f"Unexpected Flet DeprecationWarnings: {dep_warnings}")

        # Model cache bounded eviction (max 2 checkpoints kept warm for Dual-Model Benchmark)
        runs = project_data.available_model_runs()
        if len(runs) >= 2:
            inference.clear_model_cache()
            sample_pig = store.get_sample_gallery()[0]["path"]
            inference.predict(sample_pig, run_name=runs[0]["name"])
            self.assertEqual(len(inference._MODEL_RUNTIME_CACHE), 1)
            inference.predict(sample_pig, run_name=runs[1]["name"])
            self.assertLessEqual(len(inference._MODEL_RUNTIME_CACHE), inference._MAX_CACHED_MODELS)
            inference.clear_model_cache()
            self.assertEqual(len(inference._MODEL_RUNTIME_CACHE), 0)

    # --- 6. Advanced Clinical Features: Grad-CAM, Dual-Model Benchmark, Dosage Calc, Outbreak & QR ---

    def test_07_gradcam_dual_benchmark_dosage_outbreak_and_qr(self):
        """Verify Grad-CAM heatmap, Dual-Model Benchmark, Smart Dosage Calculator, Outbreak >=3/farm, and scannable QR."""
        import cv2
        import re

        page = _DummyPage()
        sample_pig = Path(store.get_sample_gallery()[0]["path"])

        # 1. Real PyTorch Grad-CAM heatmap
        gradcam_path = Path(inference_service.generate_gradcam_heatmap(sample_pig))
        self.assertTrue(gradcam_path.is_file())
        self.assertIn("gradcam_", gradcam_path.name)
        with Image.open(sample_pig) as im_orig, Image.open(gradcam_path) as im_cam:
            a_orig = np.asarray(im_orig.convert("RGB"), dtype=np.int16)
            a_cam = np.asarray(im_cam.convert("RGB"), dtype=np.int16)
            self.assertEqual(a_orig.shape, a_cam.shape)
            self.assertGreater(float(np.abs(a_orig - a_cam).mean()), 5.0)

        # 2. Dual-Model Benchmark (MobileNetV2 + EfficientNet-B0)
        bench = inference_service.predict_dual_benchmark(sample_pig)
        self.assertTrue(bench.get("ok"))
        self.assertTrue(bench.get("is_valid_pig"))
        self.assertGreaterEqual(len(bench.get("models") or []), 2)
        archs = {m.get("architecture") for m in bench["models"]}
        self.assertIn("MobileNetV2", archs)
        self.assertIn("EfficientNet-B0", archs)
        self.assertIn("badge", bench.get("consensus") or {})
        dual_card = build_dual_benchmark_card(page, bench)
        self.assertIsInstance(dual_card, ft.Control)

        # 3. Smart Dosage Calculator math + UI widget
        dose_ery = calculate_smart_dosage("Infected_Bacterial_Erysipelas", 30.0, 10)
        self.assertAlmostEqual(dose_ery["total_weight_kg"], 300.0)
        self.assertAlmostEqual(dose_ery["dose_per_pig"], 3.0)
        self.assertAlmostEqual(dose_ery["dose_total_daily"], 30.0)
        self.assertEqual(dose_ery["unit"], "ml")
        self.assertAlmostEqual(dose_ery["disinfectant_water_liters"], 8.0)
        self.assertAlmostEqual(dose_ery["disinfectant_concentrate_ml"], 80.0)

        dose_mange = calculate_smart_dosage("Infected_Parasitic_Mange", 33.0, 5)
        self.assertAlmostEqual(dose_mange["dose_per_pig"], 1.0, places=2)
        self.assertAlmostEqual(dose_mange["dose_total_daily"], 5.0, places=2)

        with self.assertRaises(ValueError):
            calculate_smart_dosage("Healthy", -5.0, 10)
        with self.assertRaises(ValueError):
            calculate_smart_dosage("Healthy", 25.0, 0)
        dosage_widget = build_smart_dosage_calculator(page, "Infected_Bacterial_Erysipelas")
        self.assertIsInstance(dosage_widget, ft.Control)

        # 4. Outbreak Warning Banner (>= 3 high-danger cases at same farm in dbo.Inspections)
        orig_db = store.DB
        orig_img_dir = store.IMAGE_DIR
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            store.DB = td_path / "test_outbreak.db"
            store.IMAGE_DIR = td_path / "imgs"
            store._SCHEMA_INITIALIZED_KEY = ""
            try:
                with patch.object(store, "read_settings", return_value={"DATABASE_ENGINE": "sqlite", "DB_NAME": "TestOB"}):
                    store.initialize(force=True)
                    info = inference.inspect_image(sample_pig)
                    fmd_res = {
                        "mode": "ai",
                        "is_valid_pig": True,
                        "label": "Infected_Viral_Foot_and_Mouth_Disease",
                        "display_label": "Lở mồm long móng (FMD)",
                        "confidence": 0.94,
                        "danger_level": "Cao",
                        "scores": [{"label": "Infected_Viral_Foot_and_Mouth_Disease", "confidence": 0.94}],
                    }
                    # 2 high-danger cases at Trại A + 1 at Trại B -> must NOT trigger >= 3/farm alert
                    store.save(info, fmd_res, case={"farm_name": "Trại An Phú A", "animal_id": "P1"}, source_image=sample_pig)
                    store.save(info, fmd_res, case={"farm_name": "Trại An Phú A", "animal_id": "P2"}, source_image=sample_pig)
                    store.save(info, fmd_res, case={"farm_name": "Trại Bình Minh B", "animal_id": "P3"}, source_image=sample_pig)
                    self.assertEqual(store.get_farm_outbreak_alerts(min_cases=3), [])
                    self.assertIsNone(auth_service.build_outbreak_alert_banner(page=page))

                    # 3rd high-danger case at Trại A -> MUST trigger outbreak banner
                    store.save(info, fmd_res, case={"farm_name": "Trại An Phú A", "animal_id": "P4"}, source_image=sample_pig)
                    alerts = store.get_farm_outbreak_alerts(min_cases=3)
                    self.assertEqual(len(alerts), 1)
                    self.assertEqual(alerts[0]["farm_name"], "Trại An Phú A")
                    self.assertEqual(alerts[0]["count"], 3)
                    banner = auth_service.build_outbreak_alert_banner(page=page)
                    self.assertIsInstance(banner, ft.Container)
            finally:
                with store._SHARED_CONN_LOCK:
                    if store._SHARED_RAW_CONN is not None:
                        try:
                            store._SHARED_RAW_CONN.close()
                        except Exception:
                            pass
                        store._SHARED_RAW_CONN = None
                        store._SHARED_ENGINE_TYPE = None
                        store._SHARED_CONN_STR = ""
                        store._SCHEMA_INITIALIZED_KEY = ""
                store.DB = orig_db
                store.IMAGE_DIR = orig_img_dir

        # 5. Real scannable QR Code (PNG base64 via qrcode+Pillow) embedded in exported A4 Clinical Report HTML
        with tempfile.TemporaryDirectory() as td_qr:
            exported_html_path = Path(
                auth_service.export_vet_report_html(
                    page,
                    {
                        "record_id": 999,
                        "case_id": "PS-000999",
                        "animal_id": "PIG-QR-77",
                        "farm_name": "Trại Thử Nghiệm QR",
                        "disease_name": "Bệnh đóng dấu lợn (Erysipelas)",
                        "predicted_class": "Infected_Bacterial_Erysipelas",
                        "confidence": 0.935,
                        "danger_level": "Cao",
                        "image_path": str(sample_pig),
                        "treatment_guide": "Tiêm Penicillin G hoặc Amoxicillin LA 15% liều 1ml/10kg TT trong 3-5 ngày.",
                    },
                    open_browser=False,
                    save_path=Path(td_qr) / "PhieuKham_PS-000999.html",
                )
            )
            self.assertTrue(exported_html_path.is_file())
            html_content = exported_html_path.read_text(encoding="utf-8")
            self.assertIn("data:image/png;base64,", html_content)
            self.assertIn("TEM SỐ #", html_content)
            m_payload = re.search(r'data-qr-payload="([^"]+)"', html_content)
            self.assertIsNotNone(m_payload, "Exported report missing data-qr-payload attribute")
            import base64
            import html as _html

            expected_payload = _html.unescape(m_payload.group(1))
            self.assertLess(len(expected_payload), 180)
            self.assertIn("PS-000999", expected_payload)
            self.assertIn("PIG-QR-77", expected_payload)

            m_img = re.search(r'id="pigskin-qr-img"\s+src="data:image/png;base64,([A-Za-z0-9+/=]+)"', html_content)
            self.assertIsNotNone(m_img, "Exported report missing base64 PNG QR <img>")
            png_bytes = base64.b64decode(m_img.group(1))
            img_bgr = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertIsNotNone(img_bgr)
            detector = cv2.QRCodeDetector()
            decoded_text, points, _ = detector.detectAndDecode(img_bgr)
            self.assertIsNotNone(points)
            self.assertEqual(decoded_text, expected_payload)

    # --- 7. Security & RBAC Package 1: PBKDF2-HMAC, Legacy Auto-Upgrade, DiseaseCatalog UPSERT, User Model Isolation & API Token ---

    def test_08_security_rbac_pbkdf2_upsert_and_api_guard(self):
        """Verify PBKDF2-HMAC salted hashing + legacy SHA-256 auto-upgrade, DiseaseCatalog UPSERT, User RBAC isolation, and FastAPI 401 guard."""
        import hashlib
        from fastapi import HTTPException
        from starlette.requests import Request

        # 1. PBKDF2-HMAC-SHA256 salted hash format & verification
        h1 = store.hash_password("MySecret123!")
        h2 = store.hash_password("MySecret123!")
        self.assertTrue(h1.startswith("pbkdf2_sha256$"))
        self.assertNotEqual(h1, h2, "Random salt must produce distinct hashes")
        self.assertTrue(store.verify_password("MySecret123!", h1))
        self.assertFalse(store.verify_password("WrongPass", h1))

        # Legacy SHA-256 hash auto-upgrade on authenticate_local + DiseaseCatalog UPSERT
        orig_db = store.DB
        with tempfile.TemporaryDirectory() as td:
            store.DB = Path(td) / "test_sec.db"
            store._SCHEMA_INITIALIZED_KEY = ""
            try:
                with patch.object(store, "read_settings", return_value={"DATABASE_ENGINE": "sqlite", "DB_NAME": "TestSec"}):
                    store.initialize(force=True)
                    legacy_sha = hashlib.sha256(b"123456").hexdigest()
                    with store.conn() as c:
                        c.execute(
                            "UPDATE users SET password_hash=? WHERE LOWER(email)=?",
                            (legacy_sha, "nongdan.pigskin@gmail.com"),
                        )
                    self.assertTrue(store.is_legacy_sha256_hash(legacy_sha))

                    # Authenticate with legacy hash -> succeeds and automatically upgrades to pbkdf2_sha256$
                    u = auth_service.authenticate_local("nongdan.pigskin@gmail.com", "123456")
                    self.assertTrue(u["password_hash"].startswith("pbkdf2_sha256$"))
                    with store.conn() as c:
                        row = c.execute(
                            "SELECT password_hash FROM users WHERE LOWER(email)=?",
                            ("nongdan.pigskin@gmail.com",),
                        ).fetchone()
                    self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))

                    # DiseaseCatalog UPSERT must preserve untouched rows and record updated_by
                    store.sync_disease_catalog_to_sql(
                        {"Healthy": {"name_vi": "Da khỏe mạnh (Updated)", "danger_level": "An toàn", "symptoms": "OK", "prevention": "OK", "treatment": "OK"}},
                        updated_by="bs.thuy.pigskin@gmail.com",
                    )
                    with store.conn() as c:
                        row_h = c.execute("SELECT name_vi, updated_by FROM DiseaseCatalog WHERE code='Healthy'").fetchone()
                        cnt_all = c.execute("SELECT COUNT(1) AS cnt FROM DiseaseCatalog").fetchone()["cnt"]
                    self.assertEqual(row_h["name_vi"], "Da khỏe mạnh (Updated)")
                    self.assertEqual(row_h["updated_by"], "bs.thuy.pigskin@gmail.com")
                    self.assertGreaterEqual(int(cnt_all), 10, "UPSERT must NOT wipe unrelated disease rows")
            finally:
                with store._SHARED_CONN_LOCK:
                    if store._SHARED_RAW_CONN is not None:
                        try:
                            store._SHARED_RAW_CONN.close()
                        except Exception:
                            pass
                        store._SHARED_RAW_CONN = None
                        store._SHARED_ENGINE_TYPE = None
                        store._SHARED_CONN_STR = ""
                        store._SCHEMA_INITIALIZED_KEY = ""
                store.DB = orig_db

        # 2. user_view.py must NEVER call set_active_checkpoint
        uv_src = (APP_ROOT / "views" / "user_view.py").read_text(encoding="utf-8")
        self.assertNotIn("set_active_checkpoint", uv_src)

        # 3. expert_view.py must NOT slice DiseaseCatalog to [:6]
        ev_src = (APP_ROOT / "views" / "expert_view.py").read_text(encoding="utf-8")
        self.assertNotIn("list(classes_cfg.items())[:6]", ev_src)

        # 4. FastAPI _require_admin must enforce ADMIN_API_TOKEN and raise 401 when missing/wrong
        repo_root = APP_ROOT.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from backend.app import main as backend_main

        def _make_req(headers: dict[str, str]) -> Request:
            raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
            return Request({"type": "http", "method": "GET", "path": "/admin/settings", "headers": raw_headers})

        with patch.dict(os.environ, {"ADMIN_API_TOKEN": "super-secret-token-2026"}, clear=False):
            # Missing token -> 401
            with self.assertRaises(HTTPException) as ctx1:
                backend_main._require_admin(_make_req({"X-Admin-Username": "admin"}))
            self.assertEqual(ctx1.exception.status_code, 401)

            # Wrong token -> 401
            with self.assertRaises(HTTPException) as ctx2:
                backend_main._require_admin(_make_req({"X-Admin-Username": "admin", "X-Admin-Token": "wrong"}))
            self.assertEqual(ctx2.exception.status_code, 401)

            # Valid token + valid admin username -> succeeds
            admin_u = backend_main._require_admin(
                _make_req({"X-Admin-Username": "admin", "X-Admin-Token": "super-secret-token-2026"})
            )
            self.assertEqual(admin_u["role"], "admin")

    # --- 8. Package 2: Model Evaluation Lab (Confusion Matrix + history.csv) & MLOps Retrain Bundle + Unapprove ---

    def test_09_model_eval_lab_and_mlops_retrain_bundle(self):
        """Verify real Confusion Matrix 10x10, history.csv Learning Curves, Unapprove (in_dataset=0), and Retrain ZIP bundle."""
        import csv
        import io
        import json
        import zipfile

        page = _DummyPage()

        # 1. Benchmark table metadata across real runs
        runs = project_data.list_model_runs()
        self.assertGreaterEqual(len(runs), 2)
        for r in runs:
            self.assertGreater(float(r.get("size_mb") or 0.0), 0.1)
            self.assertIn("seed", r)

        # 2. Confusion matrix 10x10 & history.csv from real run 20261103_125653
        ev_mnet = project_data.load_run_evaluation("20261103_125653")
        self.assertIsNotNone(ev_mnet)
        self.assertEqual(len(ev_mnet["classes"]), 10)
        cm = ev_mnet["confusion_matrix"]
        self.assertEqual(len(cm), 10)
        self.assertTrue(all(len(row) == 10 for row in cm))
        self.assertGreaterEqual(len(ev_mnet["top_confusions"]), 3)
        self.assertEqual(ev_mnet["top_confusions"][0]["true_code"], "Infected_Bacterial_Greasy_Pig_Disease")
        self.assertEqual(ev_mnet["top_confusions"][0]["pred_code"], "Infected_Parasitic_Mange")
        self.assertEqual(ev_mnet["top_confusions"][0]["count"], 11)
        self.assertTrue(ev_mnet["has_history"])
        self.assertEqual(len(ev_mnet["history"]), 24)

        # Graceful handling of run without history.csv (20261029_161050)
        ev_old = project_data.load_run_evaluation("20261029_161050")
        if ev_old is not None:
            self.assertFalse(ev_old["has_history"])
            self.assertEqual(ev_old["history"], [])
            self.assertEqual(len(ev_old["confusion_matrix"]), 10)

        # Matplotlib Learning Curves PNG render + Evaluation Lab UI mount without warnings
        loss_png, met_png = render_learning_curves_png(ev_mnet["history"], ev_mnet["best_epoch"], dark=False)
        self.assertIsNotNone(loss_png)
        self.assertIsNotNone(met_png)
        self.assertTrue(loss_png.startswith(b"\x89PNG"))
        self.assertTrue(met_png.startswith(b"\x89PNG"))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            lab_ui = build_model_evaluation_lab_card(page)
            self.assertIsInstance(lab_ui, ft.Control)
            dep_w = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
            self.assertEqual(dep_w, [], f"Unexpected DeprecationWarnings in Model Eval Lab: {dep_w}")

        # 3. Approve, Unapprove (in_dataset=0 preserving original image), and export_retrain_bundle (.zip)
        gallery = [s for s in store.get_sample_gallery() if s.get("exists")]
        self.assertGreaterEqual(len(gallery), 2)
        img1 = Path(gallery[0]["path"])
        img2 = Path(gallery[1]["path"])

        orig_db = store.DB
        orig_img_dir = store.IMAGE_DIR
        orig_curated = store.CURATED_DIR
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            store.DB = td_path / "test_mlops.db"
            store.IMAGE_DIR = td_path / "case_images"
            store.CURATED_DIR = td_path / "curated_dataset"
            exports_tmp = td_path / "exports"
            store._SCHEMA_INITIALIZED_KEY = ""
            try:
                with patch.object(store, "read_settings", return_value={"DATABASE_ENGINE": "sqlite", "DB_NAME": "TestMLOps"}):
                    store.initialize(force=True)
                    info1 = inference.inspect_image(img1)
                    info2 = inference.inspect_image(img2)
                    res1 = {
                        "mode": "ai",
                        "is_valid_pig": True,
                        "label": "Infected_Bacterial_Erysipelas",
                        "display_label": "Bệnh đóng dấu lợn",
                        "confidence": 0.92,
                        "scores": [{"label": "Infected_Bacterial_Erysipelas", "confidence": 0.92}],
                    }
                    res2 = {
                        "mode": "ai",
                        "is_valid_pig": True,
                        "label": "Infected_Parasitic_Mange",
                        "display_label": "Bệnh ghẻ Sarcoptes",
                        "confidence": 0.88,
                        "scores": [{"label": "Infected_Parasitic_Mange", "confidence": 0.88}],
                    }
                    rid1 = store.save(info1, res1, case={"animal_id": "PIG-M01", "farm_name": "Trại MLOps"}, source_image=img1)
                    rid2 = store.save(info2, res2, case={"animal_id": "PIG-M02", "farm_name": "Trại MLOps"}, source_image=img2)
                    store.submit_expert_review(rid1, True, "Infected_Bacterial_Erysipelas", "OK", "bs.thuy@pig.vn")
                    store.submit_expert_review(rid2, True, "Infected_Parasitic_Mange", "OK", "bs.thuy@pig.vn")

                    copy1 = Path(store.approve_for_dataset(rid1, True))
                    copy2 = Path(store.approve_for_dataset(rid2, True))
                    self.assertTrue(copy1.is_file())
                    self.assertTrue(copy2.is_file())

                    # Unapprove rid2 -> in_dataset = 0, copy removed, original in case_images preserved!
                    with store.conn() as c:
                        orig_path_2 = Path(c.execute("SELECT image_path FROM inspections WHERE id=?", (rid2,)).fetchone()["image_path"])
                    store.approve_for_dataset(rid2, False)
                    self.assertFalse(copy2.exists(), "Unapproved copy in curated_dataset must be deleted")
                    self.assertTrue(orig_path_2.is_file(), "Original image in case_images must remain untouched")
                    with store.conn() as c:
                        in_ds_2 = int(c.execute("SELECT in_dataset FROM inspections WHERE id=?", (rid2,)).fetchone()["in_dataset"])
                    self.assertEqual(in_ds_2, 0)

                    # Export Retrain Bundle (.zip)
                    bundle = store.export_retrain_bundle(exports_dir=exports_tmp)
                    zip_path = Path(bundle["zip_path"])
                    self.assertTrue(zip_path.is_file())
                    self.assertEqual(bundle["total_images"], 1)

                    with zipfile.ZipFile(zip_path, "r") as zf:
                        names = set(zf.namelist())
                        self.assertIn("manifest.csv", names)
                        self.assertIn("classes.json", names)
                        self.assertIn("dataset_summary.json", names)

                        manifest_rows = list(csv.DictReader(io.StringIO(zf.read("manifest.csv").decode("utf-8"))))
                        self.assertEqual(len(manifest_rows), 1)
                        self.assertEqual(
                            set(manifest_rows[0].keys()),
                            {"relative_path", "split", "labels", "group_id", "sha256"},
                        )
                        self.assertEqual(manifest_rows[0]["labels"], "Infected_Bacterial_Erysipelas")
                        self.assertEqual(manifest_rows[0]["group_id"], "PIG-M01")
                        self.assertEqual(len(manifest_rows[0]["sha256"]), 64)
                        self.assertIn(manifest_rows[0]["relative_path"], names)

                        summary = json.loads(zf.read("dataset_summary.json").decode("utf-8"))
                        self.assertEqual(summary["total_images"], 1)
                        self.assertEqual(summary["per_class_counts"]["Infected_Bacterial_Erysipelas"], 1)
                        self.assertEqual(len(summary["per_class_counts"]), 10)
            finally:
                with store._SHARED_CONN_LOCK:
                    if store._SHARED_RAW_CONN is not None:
                        try:
                            store._SHARED_RAW_CONN.close()
                        except Exception:
                            pass
                        store._SHARED_RAW_CONN = None
                        store._SHARED_ENGINE_TYPE = None
                        store._SHARED_CONN_STR = ""
                        store._SCHEMA_INITIALIZED_KEY = ""
                store.DB = orig_db
                store.IMAGE_DIR = orig_img_dir
                store.CURATED_DIR = orig_curated

    # --- 9. Export A4 Report to Downloads/FilePicker + PNG Base64 QR Verified by OpenCV ---

    def test_10_qr_png_base64_opencv_decode_and_downloads_export(self):
        """Extract base64 PNG QR directly from exported A4 HTML and decode 100% accurately via cv2.QRCodeDetector."""
        import asyncio
        import base64
        import html as _html
        import re
        import cv2

        page = _DummyPage()
        sample_pig = Path(store.get_sample_gallery()[0]["path"])

        case_payload = {
            "record_id": 1024,
            "case_id": "PS-001024",
            "animal_id": "PIG-VIP-09",
            "farm_name": "Trại An Phú - Khu A",
            "disease_name": "Bệnh đóng dấu lợn (Erysipelas)",
            "predicted_class": "Infected_Bacterial_Erysipelas",
            "confidence": 0.952,
            "danger_level": "Cao",
            "review_status": "reviewed",
            "reviewed_by": "bs.thuy.pigskin@gmail.com",
            "created_at": "2026-11-22 14:20:00",
            "image_path": str(sample_pig),
            "treatment_guide": "Tiêm Penicillin G hoặc Amoxicillin LA 15% liều 1ml/10kg TT trong 3-5 ngày.",
        }

        # Verify FilePicker save_file defaults to ~/Downloads and PhieuKham_<case_id>.html
        with tempfile.TemporaryDirectory() as td:
            chosen_target = Path(td) / "PhieuKham_PS-001024.html"
            captured_args: dict = {}

            class _FakeSavePicker:
                def __init__(self):
                    self.on_result = None

                def save_file(self, **kwargs):
                    captured_args.update(kwargs)
                    if callable(self.on_result):
                        class _Evt:
                            path = str(chosen_target)

                        self.on_result(_Evt())

            picker = _FakeSavePicker()
            asyncio.run(
                auth_service.save_vet_report_with_picker(
                    page,
                    case_payload,
                    save_picker=picker,
                    open_browser=False,
                )
            )
            self.assertEqual(captured_args.get("file_name"), "PhieuKham_PS-001024.html")
            self.assertEqual(
                Path(captured_args.get("initial_directory") or "").name.lower(),
                auth_service._default_downloads_dir().name.lower(),
            )
            self.assertTrue(chosen_target.is_file())

            html_doc = chosen_target.read_text(encoding="utf-8")
            self.assertIn("In phiếu / Lưu thành PDF", html_doc)
            self.assertIn("window.print()", html_doc)
            self.assertIn("@media print", html_doc)
            self.assertIn("image-rendering: pixelated", html_doc)
            self.assertIn("width: 150px; height: 150px;", html_doc)

            # Extract embedded PNG base64 directly from the <img> tag and decode with OpenCV
            m_img = re.search(r'id="pigskin-qr-img"\s+src="data:image/png;base64,([A-Za-z0-9+/=]+)"', html_doc)
            self.assertIsNotNone(m_img, "Missing base64 PNG QR <img> in exported HTML")
            png_bytes = base64.b64decode(m_img.group(1))
            self.assertTrue(png_bytes.startswith(b"\x89PNG"))

            img_bgr = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertIsNotNone(img_bgr)
            # Confirm 4-module white Quiet Zone border is pure white on all corners
            self.assertTrue(np.all(img_bgr[0, 0] == 255))
            self.assertTrue(np.all(img_bgr[-1, -1] == 255))
            self.assertTrue(np.all(img_bgr[0, -1] == 255))
            self.assertTrue(np.all(img_bgr[-1, 0] == 255))

            decoded_text, points, _ = cv2.QRCodeDetector().detectAndDecode(img_bgr)
            self.assertIsNotNone(points, "OpenCV QRCodeDetector failed to locate QR finder patterns")

            m_payload = re.search(r'data-qr-payload="([^"]+)"', html_doc)
            expected_payload = _html.unescape(m_payload.group(1))
            self.assertEqual(decoded_text, expected_payload)
            self.assertLess(len(decoded_text), 180)
            self.assertIn("PIGSKINTECH - HO SO BENH AN", decoded_text)
            self.assertIn("Ma ca: PS-001024", decoded_text)
            self.assertIn("Ma heo: PIG-VIP-09", decoded_text)
            self.assertIn("Do tin cay: 95.2%", decoded_text)
            self.assertIn("Trang thai: Da tham dinh", decoded_text)
            self.assertIn("Ngay: 2026-11-22", decoded_text)

        # Static Flutter layout guard: NEVER put expand=True child directly inside ft.Row(..., wrap=True)
        import ast

        violations: list[str] = []
        for py_file in sorted(APP_ROOT.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                    if name == "Row" and any(
                        kw.arg == "wrap" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                        for kw in node.keywords
                    ):
                        ctrl_arg = node.args[0] if node.args else next((kw.value for kw in node.keywords if kw.arg == "controls"), None)
                        if isinstance(ctrl_arg, (ast.List, ast.Tuple)):
                            for elt in ctrl_arg.elts:
                                if isinstance(elt, ast.Call):
                                    for kw in elt.keywords:
                                        if kw.arg == "expand" and not (isinstance(kw.value, ast.Constant) and kw.value.value in (False, None, 0)):
                                            violations.append(f"{py_file.name}:{node.lineno} -> child line {elt.lineno}")
        self.assertEqual(violations, [], f"Flutter Wrap+Expanded layout crash detected: {violations}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
