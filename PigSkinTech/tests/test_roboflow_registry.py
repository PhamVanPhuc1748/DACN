"""Roboflow registration, worker selection and DB isolation on devN."""
from pathlib import Path
import importlib.util
import math
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from PIL import Image
from services import inference


class RoboflowRegistryTest(unittest.TestCase):
    def test_import_store_does_not_connect(self):
        check = """
from unittest.mock import patch
from services import database
with patch.object(database, '_connect', side_effect=AssertionError('Database opened')) as connect:
    from services import store
    connect.assert_not_called()
    assert not store._initialized
"""
        subprocess.run([sys.executable, '-B', '-c', check],
                       cwd=Path(__file__).resolve().parents[1], check=True)

    def test_default_and_roboflow_assets(self):
        self.assertTrue(inference.model_ready())
        self.assertEqual(inference.model_spec()['run_id'], inference.DEFAULT_MODEL_ID)
        run = inference.ROBOFLOW_RUN
        self.assertTrue(inference.model_ready(run))
        self.assertEqual(inference.labels(run), inference.labels())
        self.assertEqual(len(inference.labels(run)), 10)
        spec = inference.model_spec(run)
        self.assertEqual(spec['preprocessing'], {
            'resize': [224, 224], 'color_mode': 'RGB',
            'normalization': {'mean': [.485, .456, .406], 'std': [.229, .224, .225]}})
        with self.assertRaises(ValueError):
            inference.model_paths('../unregistered')

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('torchvision'),
                         'Requires optional PyTorch runtime')
    def test_real_cpu_switch_in_persistent_worker(self):
        with TemporaryDirectory() as temp:
            fixture = Path(temp) / 'test.png'
            Image.new('RGB', (80, 72), (161, 94, 69)).save(fixture)
            worker = inference.AIWorkerClient(sys.executable, worker_environment={'OMP_NUM_THREADS': '2'})
            try:
                old = worker.predict(fixture)
                pid = worker.pid
                baseline = worker.predict(fixture, inference.ROBOFLOW_RUN)
                back = worker.predict(fixture, inference.DEFAULT_MODEL_ID)
                self.assertEqual(pid, worker.pid)
            finally:
                worker.close()
            self.assertIn(inference.DEFAULT_MODEL_ID, old['model_info'])
            self.assertIn(inference.ROBOFLOW_RUN, baseline['model_info'])
            self.assertEqual(old['scores'], back['scores'])
            scores = baseline['scores']
            self.assertEqual({item['label'] for item in scores}, set(inference.labels()))
            self.assertTrue(all(math.isfinite(item['confidence']) for item in scores))
            self.assertAlmostEqual(sum(item['confidence'] for item in scores), 1.0, places=6)
