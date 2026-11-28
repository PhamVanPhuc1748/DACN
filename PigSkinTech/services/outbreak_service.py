"""Summarize the latest inspections within each farm in one user's history."""
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import unicodedata

from services.project_data import get_class_info


RECENT_INSPECTION_LIMIT = 10
EXISTING_ALERT_COUNT = 2
HIGH_DANGER_LEVELS = {"Cao", "Khẩn cấp"}


@dataclass
class FarmSurveillance:
    name: str
    inspections: int = 0
    animals: int = 0
    unidentified_inspections: int = 0
    repeated_images: int = 0
    suspected: list[str] = field(default_factory=list)
    expert_confirmed: list[str] = field(default_factory=list)


def _identifier(value: str | None) -> str:
    return unicodedata.normalize("NFC", " ".join((value or "").split())).casefold()


def _inspection_time(record: dict) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(record.get("created_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min
    if timestamp.tzinfo is not None:
        return timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    return timestamp


def _image_digest(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with Path(path).open("rb") as image:
            digest = hashlib.sha256()
            for block in iter(lambda: image.read(65536), b""):
                digest.update(block)
            return digest.hexdigest()
    except OSError:
        return None


def summarize_surveillance(records: list[dict]) -> list[FarmSurveillance]:
    """Use the existing ten-inspection window and count each known animal once per farm."""
    recent = sorted(records or [], key=_inspection_time, reverse=True)[:RECENT_INSPECTION_LIMIT]
    farms: dict[str, FarmSurveillance] = {}
    histories: dict[tuple[str, str], list[dict]] = {}
    for record in recent:
        farm = _identifier(record.get("farm_name"))
        if farm in ("", "trại chăn nuôi"):
            continue
        summary = farms.setdefault(farm, FarmSurveillance(name=record["farm_name"].strip()))
        summary.inspections += 1
        animal = _identifier(record.get("animal_id"))
        if animal in ("", "pig-new"):
            summary.unidentified_inspections += 1
            continue
        histories.setdefault((farm, animal), []).append(record)

    for (farm, _animal), history in histories.items():
        summary = farms[farm]
        summary.animals += 1
        if len(history) > 1:
            digests = [_image_digest(record.get("image_path")) for record in history]
            known_digests = [digest for digest in digests if digest]
            summary.repeated_images += len(known_digests) - len(set(known_digests))

        # Within the window, prefer the newest reviewed label for this animal.
        reviewed = next((r for r in history if r.get("review_status") == "reviewed" and r.get("expert_label")), None)
        label = reviewed["expert_label"] if reviewed else history[0].get("predicted_class")
        if label and get_class_info(label).get("danger_level") in HIGH_DANGER_LEVELS:
            destination = summary.expert_confirmed if reviewed else summary.suspected
            destination.append(label)
    return list(farms.values())
