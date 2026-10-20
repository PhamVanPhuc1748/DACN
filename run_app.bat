@echo off
chcp 65001 >nul
echo =====================================================================
echo    KHỞI CHẠY HỆ THỐNG PHÁT HIỆN BỆNH TRÊN DA HEO (DESKTOP APP)
echo =====================================================================
echo.

echo [1/3] Đang khởi động Backend FastAPI (Port 8000)...
start "PigSkin Backend API" cmd /k "E:\code\DACN\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload"

echo [2/3] Đang khởi động Desktop Frontend UI (Port 5173)...
start "PigSkin Desktop UI" cmd /k "npm --prefix frontend run dev"

echo [3/3] Đang mở trình duyệt giao diện Desktop...
timeout /t 3 /nobreak >nul
start http://localhost:5173/

echo.
echo =====================================================================
echo    He thong da khoi dong thanh cong!
echo    - Frontend UI: http://localhost:5173/
echo    - Backend API: http://127.0.0.1:8000/docs
echo =====================================================================
pause
