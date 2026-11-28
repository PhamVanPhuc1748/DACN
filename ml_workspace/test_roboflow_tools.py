"""Regression tests for local audit and reviewed manifest generation."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from audit_roboflow import find_groups, write_csv
from build_roboflow_manifest import CLASSES, build, load_classes
from review_roboflow import load_review, save_review


class RoboflowToolsTest(unittest.TestCase):
    def test_chain_is_not_an_all_pairs_match(self):
        bits = np.zeros((4, 256), dtype=bool)
        bits[1, :12] = True
        bits[2, :24] = True
        bits[3, 100:140] = True
        self.assertEqual(find_groups(bits, 12), [[0, 1, 2]])
        self.assertEqual(np.count_nonzero(bits[0] != bits[2]), 24)

    def test_pending_and_confirmed_cross_split_group(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, audit = base / "images", base / "audit"
            audit.mkdir()
            for index, label in enumerate(load_classes(CLASSES)):
                for number, split in enumerate(("train", "valid", "test")):
                    path = root / split / label / "échantillon.png"
                    path.parent.mkdir(parents=True)
                    Image.new("RGB", (8, 8), (index, number, 7)).save(path)
            extra = root / "train/Healthy/variant.png"
            Image.new("RGB", (8, 8), (99, 0, 7)).save(extra)
            candidates = [extra.relative_to(root).as_posix(), "test/Healthy/échantillon.png"]
            rows = {path: dict(path=path, candidate_group="G001", disposition="", confirmed_group="", notes="")
                    for path in candidates}
            write_csv(audit / "group_members.csv", ["path"], [{"path": path} for path in candidates])
            write_csv(audit / "unreadable.csv", ["path"], [])
            write_csv(audit / "similarity_review.csv", list(next(iter(rows.values()))), rows.values())
            decisions = base / "decisions.csv"
            review = load_review(audit, decisions)
            self.assertEqual(review, rows)
            save_review(decisions, review)
            with self.assertRaisesRegex(ValueError, "await review"):
                build(root, audit, decisions, base / "draft")
            self.assertFalse((base / "draft").exists())
            for row in review.values():
                row.update(disposition="include", confirmed_group="related")
            save_review(decisions, review)
            self.assertEqual(load_review(audit, decisions), review)
            result = build(root, audit, decisions, base / "draft")
            self.assertEqual(result["split_counts"], {"train": 10, "val": 10, "test": 11})
            self.assertEqual(result["changed_splits"], 1)
            self.assertTrue(extra.is_file())


if __name__ == "__main__":
    unittest.main()
