"""Pure validation tests; no application database is imported or opened."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from services import inference
from services.experiment_metrics import load_experiment_metrics
from services.dataset_audit import audit_dataset


class ImageValidationTests(unittest.TestCase):
    def test_integrated_model_assets_and_training_preprocessing_are_verified(self):
        self.assertTrue(inference.model_ready())
        specification = inference.model_spec()
        self.assertEqual(specification['run_id'], '20261103_125653')
        self.assertEqual(specification['architecture'], 'mobilenet_v2')
        self.assertEqual(specification['preprocessing']['resize'], [224, 224])
        self.assertEqual(len(inference.labels()), 10)

    def test_checkpoint_hash_mismatch_is_not_ready(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            weights = folder / 'best.pth'
            classes = folder / 'classes.json'
            manifest = folder / 'model_manifest.json'
            weights.write_bytes(b'tampered')
            classes.write_text(json.dumps([f'class-{index}' for index in range(10)]),
                               encoding='utf-8')
            manifest.write_text(json.dumps({
                'run_id': 'test', 'architecture': 'mobilenet_v2',
                'checkpoint_sha256': '0' * 64, 'manifest_sha256': '1' * 64,
                'classes_sha256': '2' * 64, 'class_count': 10,
                'preprocessing': {'resize': [224, 224]}, 'validation': {},
            }), encoding='utf-8')
            with patch.object(inference, 'WEIGHTS', weights), patch.object(
                    inference, 'CLASSES', classes), patch.object(
                    inference, 'MODEL_MANIFEST', manifest):
                self.assertFalse(inference.model_ready())

    def test_rejects_non_image_with_supported_extension(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'bad.jpg'
            path.write_bytes(b'not an image')
            with self.assertRaises(ValueError):
                inference.inspect_image(path)

    def test_rejects_excessive_pixels(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'large.png'
            Image.new('RGB', (20, 20)).save(path)
            with patch.object(inference, 'MAX_PIXELS', 399):
                with self.assertRaisesRegex(ValueError, 'pixel'):
                    inference.inspect_image(path)

    def test_missing_checkpoint_has_no_prediction(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'sample.png'
            Image.new('RGB', (20, 20)).save(path)
            with patch.object(inference, 'model_ready', return_value=False):
                result = inference.predict(path)
            self.assertEqual(result['mode'], 'unavailable')
            self.assertIsNone(result['label'])
            self.assertIsNone(result['confidence'])
            self.assertEqual(result['scores'], [])

    def test_exif_orientation_is_applied_to_display_dimensions(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'rotated.jpg'
            exif = Image.Exif()
            exif[274] = 6
            Image.new('RGB', (40, 20)).save(path, exif=exif)
            info = inference.inspect_image(path)
            self.assertEqual((info['width'], info['height']), (20, 40))

    def test_relative_ai_runtime_candidate_is_resolved_from_runtime_config(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            model_folder = folder / 'models'
            runtime_folder = folder / 'ai_runtime'
            model_folder.mkdir()
            runtime_folder.mkdir()
            executable = runtime_folder / 'python.exe'
            executable.write_bytes(b'placeholder')
            config = model_folder / 'runtime.json'
            config.write_text(json.dumps({
                'python_executable': '',
                'python_candidates': ['../ai_runtime/python.exe'],
            }), encoding='utf-8')
            with patch.object(inference, 'RUNTIME_CONFIG', config), patch.object(
                    inference, 'EXECUTABLE_DIR', folder / 'app'), patch.object(
                    inference, 'ROOT', folder), patch.dict(
                    inference.os.environ, {'PIGSKIN_AI_PYTHON': ''}):
                self.assertEqual(inference._external_python(), executable.resolve())


class ExperimentValidationTests(unittest.TestCase):
    def test_optional_loss_and_confusion_matrix_are_read_from_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'run.json'
            path.write_text(json.dumps({
                'metrics': {'test_accuracy': 0.75, 'train_loss': 1.25},
                'per_class': [{'class_name': 'A'}, {'class_name': 'B'}],
                'confusion_matrix': [[2, 1], [0, 1]],
            }), encoding='utf-8')
            report = load_experiment_metrics(path)
            self.assertEqual(report['losses']['train_loss'], 1.25)
            self.assertEqual(report['confusion_matrix'][0], [2, 1])

    def test_invalid_confusion_matrix_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'run.json'
            path.write_text(json.dumps({
                'metrics': {'test_accuracy': 0.75},
                'per_class': [{'class_name': 'A'}],
                'confusion_matrix': [[-1]],
            }), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_experiment_metrics(path)


class DatasetAuditTests(unittest.TestCase):
    def test_reports_only_manifest_version_and_scanned_images(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / 'dataset_manifest.json').write_text(
                json.dumps({'version': 'v1.2'}), encoding='utf-8')
            image_dir = folder / 'train' / 'healthy'
            image_dir.mkdir(parents=True)
            Image.new('RGB', (16, 16)).save(image_dir / 'sample.png')
            report = audit_dataset(folder)
            self.assertEqual(report['dataset_version'], 'v1.2')
            self.assertEqual(report['valid_images'], 1)
            self.assertEqual(report['split_counts']['train'], 1)
