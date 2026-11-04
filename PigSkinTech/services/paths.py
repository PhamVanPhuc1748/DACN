"""Portable resource and writable-data locations for source and frozen builds."""

import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FROZEN = bool(getattr(sys, 'frozen', False))
RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', PROJECT_ROOT)).resolve()
EXECUTABLE_DIR = (
    Path(sys.executable).resolve().parent if FROZEN else PROJECT_ROOT
)


def _configured_directory(name):
    value = os.environ.get(name, '').strip()
    if not value:
        return None
    return Path(os.path.expandvars(value)).expanduser().resolve()


def writable_data_root():
    configured = _configured_directory('PIGSKIN_DATA_DIR')
    if configured is not None:
        return configured
    if not FROZEN:
        return PROJECT_ROOT
    local_app_data = os.environ.get('LOCALAPPDATA', '').strip()
    base = Path(local_app_data) if local_app_data else Path.home() / 'AppData' / 'Local'
    return (base / 'PigSkinAIStudio').resolve()


DATA_ROOT = writable_data_root()


def model_root():
    configured = _configured_directory('PIGSKIN_MODEL_DIR')
    if configured is not None:
        return configured
    adjacent = EXECUTABLE_DIR / 'models'
    if FROZEN and adjacent.is_dir():
        return adjacent
    return RESOURCE_ROOT / 'models'

