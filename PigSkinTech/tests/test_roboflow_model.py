"""Bundled baseline registration and in-process inference."""
import math
import secrets
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import inference, project_data
from services import auth_service, store


RUN = "rf_v1_conservative_baseline_01"


class RoboflowModelTest(unittest.TestCase):
    def test_import_does_not_open_application_database(self):
        check = """
from unittest.mock import patch
from services import config_store
with patch.object(config_store, 'read_settings', return_value={'DATABASE_ENGINE': 'sqlite'}) as settings:
    from services import store
    settings.assert_not_called()
    assert store._SHARED_RAW_CONN is None
"""
        subprocess.run([sys.executable, "-B", "-c", check], cwd=Path(__file__).resolve().parents[1], check=True)

    def test_demo_accounts_model_switch_and_review_in_temporary_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            demo = (("nongdan.pigskin@gmail.com", "user"), ("bs.thuy.pigskin@gmail.com", "expert"),
                    ("admin.pigskin@gmail.com", "admin"))
            demo_password = secrets.token_urlsafe(24)
            with patch.multiple(store, DB=root / "test.db", IMAGE_DIR=root / "images",
                                read_settings=lambda: {"DATABASE_ENGINE": "sqlite",
                                                       "PIGSKIN_DEMO_MODE": "true",
                                                       "PIGSKIN_DEMO_PASSWORD": demo_password}, pyodbc=None,
                                _SHARED_RAW_CONN=None, _SHARED_ENGINE_TYPE=None, _SHARED_CONN_STR="",
                                _SCHEMA_INITIALIZED_KEY=None, _ACTIVE_DB_INFO={}), \
                 patch.object(project_data, "ACTIVE_MODEL_STATE_PATH", root / "active.json"):
                try:
                    store.initialize()
                    for email, role in demo:
                        self.assertEqual(auth_service.authenticate_local(email, demo_password)["role"], role)
                    for version in (RUN, "20261103_125653"):
                        selected = project_data.active_run(version)
                        self.assertEqual(project_data.set_active_checkpoint(str(selected["checkpoint"]))["name"], version)
                    image = root / "fixture.png"
                    Image.new("RGB", (24, 24)).save(image)
                    record = store.save(inference.inspect_image(image), {"label": "Healthy", "confidence": .8},
                                        {"user_email": demo[0][0]}, source_image=image)
                    self.assertTrue(any(row["id"] == record for row in store.list_user_inspections(demo[0][0])))
                    store.request_expert_review(record)
                    self.assertIn(record, {row["id"] for row in store.list_review_queue()})
                    with self.assertRaises(ValueError):
                        store.submit_expert_review(record, False, "", "QA fixture", demo[1][0])
                    self.assertIn(record, {row["id"] for row in store.list_review_queue()})
                    store.submit_expert_review(record, True, "Healthy", "QA fixture", demo[1][0])
                    self.assertNotIn(record, {row["id"] for row in store.list_review_queue()})
                finally:
                    if store._SHARED_RAW_CONN is not None:
                        store._SHARED_RAW_CONN.close()

    def test_registration_and_cpu_predictions(self):
        import torch

        torch.set_num_threads(min(4, torch.get_num_threads()))
        run = project_data.active_run(RUN)
        self.assertEqual(run["name"], RUN)
        self.assertIn("Roboflow Baseline", run["model_label"])
        self.assertEqual(len(run["config"]["classes"]), 10)
        self.assertEqual(run["config"]["class_to_index"],
                         {name: i for i, name in enumerate(run["config"]["classes"])})
        self.assertIn(RUN, {item["run_name"] for item in project_data.list_model_runs()})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(project_data, "ACTIVE_MODEL_STATE_PATH", root / "active.json"):
                self.assertNotEqual(project_data.active_run()["name"], RUN)
            inference._MODEL_RUNTIME_CACHE.clear()
            for ext in ("jpg", "png"):
                path = root / f"fixture.{ext}"
                Image.new("RGB", (64, 79), (180, 118, 100)).save(path)
                inference.inspect_image(path)
                with patch.object(torch.cuda, "is_available", return_value=False):
                    first = inference._predict_inprocess(path, run)
                    second = inference._predict_inprocess(path, run)
                self.assertEqual(first["all_scores"], second["all_scores"])
                self.assertIn("CPU", first["model_info"])
                scores = first["all_scores"]
                self.assertEqual({row["label"] for row in scores}, set(run["config"]["classes"]))
                self.assertTrue(all(math.isfinite(row["confidence"]) for row in scores))
                self.assertAlmostEqual(sum(row["confidence"] for row in scores), 1, places=6)
            invalid = root / "broken.jpg"
            invalid.write_bytes(b"not a JPEG")
            with self.assertRaises(ValueError):
                inference.inspect_image(invalid)
            with self.assertRaises(FileNotFoundError):
                project_data.read_checkpoint_details(root / "missing.pt")
            bad = root / "best_model.pt"
            bad.touch()
            (root / "config.json").write_text("{", encoding="utf-8")
            (root / "final_metrics.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                project_data.read_checkpoint_details(bad)
            inference._MODEL_RUNTIME_CACHE.clear()
