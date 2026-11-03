import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import readiness


class ReadinessTests(unittest.TestCase):
    def test_image_health_reports_missing_and_outside_paths_without_exposing_them(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / 'case_images'
            archive.mkdir()
            existing = archive / 'existing.jpg'
            existing.write_bytes(b'image')
            missing = archive / 'missing.jpg'
            outside = Path(root) / 'outside.jpg'
            outside.write_bytes(b'image')
            with patch.object(readiness, 'IMAGE_DIR', archive):
                report = readiness._archived_image_health(
                    [str(existing), str(missing), str(outside), '']
                )
        self.assertEqual(report, {'checked': 3, 'missing': 1, 'outside_archive': 1})
