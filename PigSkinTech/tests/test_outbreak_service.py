"""Regression checks for farm, animal, and review boundaries."""
import sys
import tempfile
import unittest
from pathlib import Path

import flet as ft

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.auth_service import build_outbreak_alert_banner, ensure_flet_compat
from services.outbreak_service import summarize_surveillance


SWINEPOX = "Infected_Viral_Swinepox"


def inspection(animal="PIG-1", farm="Farm A", minute=0, **fields):
    return {
        "animal_id": animal,
        "farm_name": farm,
        "created_at": f"2026-11-29 09:{minute:02d}:00",
        "predicted_class": SWINEPOX,
        **fields,
    }


def banner_text(control):
    if isinstance(control, ft.Text):
        return control.value
    return "\n".join(banner_text(child) for child in control._get_children())


class OutbreakTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_flet_compat()

    def test_same_image_and_animal_at_different_times_is_one_suspected_case(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.webp"
            second = Path(directory) / "second.webp"
            first.write_bytes(b"identical image bytes")
            second.write_bytes(first.read_bytes())
            records = [
                inspection(image_path=str(first)),
                inspection(animal=" pig-1 ", farm=" FARM  A ", minute=3, image_path=str(second)),
            ]
            farm, = summarize_surveillance(records)
            self.assertEqual((farm.inspections, farm.animals, farm.repeated_images), (2, 1, 1))
            self.assertEqual(farm.suspected, [SWINEPOX])
            self.assertIsNone(build_outbreak_alert_banner(records))
            self.assertEqual(len(records), 2)

    def test_same_image_for_distinct_identified_animals_preserves_both(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.webp"
            image.write_bytes(b"identical image bytes")
            records = [inspection(animal, image_path=str(image)) for animal in ("PIG-1", "PIG-2")]
            farm, = summarize_surveillance(records)
            self.assertEqual((farm.animals, farm.repeated_images), (2, 0))
            self.assertIn("2/2 cá thể", banner_text(build_outbreak_alert_banner(records)))

    def test_same_animal_code_is_independent_across_farms_but_alerts_are_local(self):
        records = [inspection(), inspection(farm="Farm B")]
        farms = summarize_surveillance(records)
        self.assertEqual([farm.animals for farm in farms], [1, 1])
        self.assertIsNone(build_outbreak_alert_banner(records))
        records.append(inspection("PIG-2"))
        text = banner_text(build_outbreak_alert_banner(records))
        self.assertIn("Farm A", text)
        self.assertNotIn("Farm B", text)

    def test_denominator_below_ten_excludes_repeats_and_missing_identity(self):
        records = [
            inspection(),
            inspection(minute=1),
            inspection("PIG-2"),
            inspection("PIG-3", predicted_class="Healthy"),
            inspection("PIG-NEW"),
            inspection(""),
            inspection("PIG-4", farm="Trại chăn nuôi"),
        ]
        farm, = summarize_surveillance(records)
        self.assertEqual((farm.inspections, farm.animals, farm.unidentified_inspections), (6, 3, 2))
        text = banner_text(build_outbreak_alert_banner(records))
        self.assertIn("2/3 cá thể", text)
        self.assertIn("6 lượt khám", text)

    def test_reviewed_diagnoses_are_separate_from_suspicions(self):
        confirmed = inspection(review_status="reviewed", expert_label=SWINEPOX)
        suspect = inspection("PIG-2", expert_label="Healthy", review_status="needs_review")
        mixed_text = banner_text(build_outbreak_alert_banner([confirmed, suspect]))
        self.assertEqual(mixed_text.count("1/2 cá thể"), 2)
        corrected = inspection("PIG-2", minute=1, review_status="reviewed", expert_label="Healthy")
        repeat = inspection("PIG-2", minute=2)
        farm, = summarize_surveillance([repeat, confirmed, suspect, corrected])
        self.assertEqual(farm.expert_confirmed, [SWINEPOX])
        self.assertEqual(farm.suspected, [])
        text = banner_text(build_outbreak_alert_banner([
            confirmed, inspection("PIG-2", review_status="reviewed", expert_label=SWINEPOX),
            inspection("PIG-3"), inspection("PIG-4"),
        ]))
        self.assertIn("Cảnh báo theo ca đã được chuyên gia xác nhận", text)
        self.assertIn("Cảnh báo nguy cơ từ AI", text)
        self.assertEqual(text.count("2/4 cá thể"), 2)

    def test_window_keeps_latest_ten_by_inspection_time(self):
        records = [inspection("PIG-2"), inspection(minute=1)]
        records += [inspection(minute=minute) for minute in range(2, 12)]
        farm, = summarize_surveillance(records)
        self.assertEqual((farm.inspections, farm.animals), (10, 1))
        self.assertIsNone(build_outbreak_alert_banner(records))


if __name__ == "__main__":
    unittest.main()
