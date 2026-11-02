"""
Script khởi động ứng dụng Desktop PigSkin AI Studio (Flet)
"""

import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PIGSKIN_DIR = BASE_DIR / "PigSkinTech"
VENV_PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"

def main():
    python_bin = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
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
