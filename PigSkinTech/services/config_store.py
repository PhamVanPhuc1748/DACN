"""Read and safely update the local backend/.env settings file."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / "backend" / ".env"


def _parse_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
        if raw.strip().startswith('"'):
            value = value.replace('\\"', '"').replace("\\\\", "\\")
        return value
    return value.split(" #", 1)[0].strip()


def read_settings() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.is_file():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if separator and key.strip():
            values[key.strip()] = _parse_value(value)
    return values


def _serialize_value(value: str) -> str:
    clean = str(value).replace("\r", "").replace("\n", " ")
    if any(char.isspace() for char in clean) or "#" in clean or '"' in clean:
        return '"' + clean.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return clean


def save_settings(updates: dict[str, str | None]) -> None:
    """Update managed keys while retaining comments and unrelated settings.

    A ``None`` value means preserve the existing setting. The UI uses this for
    secret fields so a blank password box cannot erase a saved credential.
    """
    updates = {key: value for key, value in updates.items() if value is not None}
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    original = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    output: list[str] = []
    seen: set[str] = set()

    for line in original:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in updates:
                output.append(f"{key}={_serialize_value(updates[key])}")
                seen.add(key)
                continue
        output.append(line)

    if not original:
        output.extend(
            [
                "# PigSkinTech local settings. Keep this file private and out of Git.",
                "# Updated from the Admin > Cấu hình hệ thống screen.",
            ]
        )
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={_serialize_value(value)}")

    temp_path = ENV_PATH.with_suffix(".env.tmp")
    temp_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.replace(temp_path, ENV_PATH)
