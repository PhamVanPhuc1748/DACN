"""
Script khởi động toàn diện hệ thống Pig Skin Disease Detection
Bao gồm:
  1. Backend API (FastAPI trên Uvicorn - Port 8000)
  2. Frontend Desktop UI (React + Vite - Port 5173)
  3. Tự động kiểm tra trạng thái và mở trình duyệt
  4. Quản lý dừng an toàn cả 2 tiến trình khi bấm Ctrl+C
"""

import os
import sys
import time
import signal
import shutil
import urllib.request
import webbrowser
import subprocess
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
VENV_PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"

# Cấu hình cổng và URL
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
FRONTEND_PORT = 5173
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

processes = []

def print_banner():
    banner = """
========================================================================
    HE THONG PHAT HIEN BENH TREN DA HEO (DESKTOP APPLICATION)
========================================================================
    * Backend API : {backend_url}
    * Frontend UI : {frontend_url}
    * API Docs    : {backend_url}/docs
========================================================================
    Nhan Ctrl + C bat cu luc nao de dung toan bo he thong.
------------------------------------------------------------------------
""".format(backend_url=BACKEND_URL, frontend_url=FRONTEND_URL)
    print(banner)

def get_python_exec():
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable

def get_npm_exec():
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("Khong tim thay Node.js / npm tren he thong. Vui long cai dat Node.js.")
    return npm

def wait_for_service(url, timeout=20, name="Service"):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def cleanup(signum=None, frame=None):
    print("\n\n[!] Dang tat toan bo tien trinh Backend va Frontend...")
    for p in processes:
        try:
            if p.poll() is None:
                # Tren Windows, dung taskkill de dong sach cay tien trinh con
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    p.terminate()
        except Exception:
            pass
    print("[v] Da tat he thong an toan. Hen gap lai!")
    sys.exit(0)

def main():
    print_banner()

    # Dang ky bo lang nghe tin hieu dung
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    python_bin = get_python_exec()
    npm_bin = get_npm_exec()

    # 1. Khoi dong Backend
    print("[1/3] Dang khoi dong Backend FastAPI tai port 8000...")
    backend_cmd = [
        python_bin,
        "-m", "uvicorn",
        "app.main:app",
        "--app-dir", str(BACKEND_DIR),
        "--host", BACKEND_HOST,
        "--port", str(BACKEND_PORT),
        "--reload"
    ]
    p_backend = subprocess.Popen(
        backend_cmd,
        cwd=str(BASE_DIR)
    )
    processes.append(p_backend)

    # 2. Khoi dong Frontend
    print("[2/3] Dang khoi dong Desktop Frontend UI tai port 5173...")
    frontend_cmd = [npm_bin, "run", "dev"]
    p_frontend = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR)
    )
    processes.append(p_frontend)

    # 3. Kiem tra ket noi & Mo trinh duyet
    print("[3/3] Dang kiem tra trang thai cac dich vu...")
    backend_ok = wait_for_service(f"{BACKEND_URL}/health", timeout=15, name="Backend")
    frontend_ok = wait_for_service(FRONTEND_URL, timeout=15, name="Frontend")

    if backend_ok and frontend_ok:
        print("\n[OK] Toan bo he thong da san sang!")
        print(f"[*] Dang mo trinh duyet toi: {FRONTEND_URL}")
        try:
            webbrowser.open(FRONTEND_URL)
        except Exception:
            pass
    else:
        print("\n[Canh bao] Mot trong cac dich vu mat nhieu thoi gian hon de san sang.")
        print(f"Trang thai Backend: {'SAN SANG' if backend_ok else 'DANG KHOI DONG'}")
        print(f"Trang thai Frontend: {'SAN SANG' if frontend_ok else 'DANG KHOI DONG'}")
        print(f"Ban co the truy cap truc tiep tai: {FRONTEND_URL}")

    print("\n>>> He thong dang hoat dong. Nhan Ctrl + C de dung lai <<<\n")

    # Giu tien trinh chinh hoat dong
    try:
        while True:
            time.sleep(1)
            # Kiem tra neu tien trinh con bi sup
            if p_backend.poll() is not None:
                print("[!] Backend da dung dot ngot.")
                break
            if p_frontend.poll() is not None:
                print("[!] Frontend da dung dot ngot.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main()
