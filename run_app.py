"""
Script khởi động ứng dụng Desktop PigSkin AI Studio (Flet)
"""

import importlib.util
import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PIGSKIN_DIR = BASE_DIR / "PigSkinTech"
VENV_CANDIDATES = (
    BASE_DIR / "venv" / "Scripts" / "python.exe",
    BASE_DIR / ".venv" / "Scripts" / "python.exe",
    PIGSKIN_DIR / ".venv" / "Scripts" / "python.exe",
    PIGSKIN_DIR / "venv" / "Scripts" / "python.exe",
)


def _has_flet(python_exe: str | Path) -> bool:
    if str(Path(python_exe).resolve()) == str(Path(sys.executable).resolve()):
        return importlib.util.find_spec("flet") is not None
    try:
        res = subprocess.run(
            [str(python_exe), "-c", "import flet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return res.returncode == 0
    except Exception:
        return False


def _resolve_python_bin() -> str:
    for cand in VENV_CANDIDATES:
        if cand.is_file() and _has_flet(cand):
            return str(cand)
    if _has_flet(sys.executable):
        return sys.executable
    local_py_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    if local_py_root.is_dir():
        for py_dir in sorted(local_py_root.glob("Python*"), reverse=True):
            exe = py_dir / "python.exe"
            if exe.is_file() and _has_flet(exe):
                return str(exe)
    return sys.executable


def main():
    python_bin = _resolve_python_bin()
    print("=" * 72)
    print("   PIGSKIN AI STUDIO - UNG DUNG DESKTOP NGHIEN CUU (FLET)")
    print("=" * 72)
    print(f"[*] Thu muc ung dung: {PIGSKIN_DIR}")
    print(f"[*] Python runtime   : {python_bin}")
    print("[*] Dang khoi dong giao dien Desktop...")
    print("-" * 72)

    cmd = [python_bin, "main.py"]
    try:
        subprocess.run(cmd, cwd=str(PIGSKIN_DIR), check=True)
    except KeyboardInterrupt:
        print("\n[!] Da dung ung dung.")
    except Exception as e:
        print(f"\n[!] Gap loi khi khoi chay ung dung: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
