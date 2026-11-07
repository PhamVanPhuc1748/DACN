@echo off
chcp 65001 >nul
title PigSkin AI Studio - Desktop App
cd /d "%~dp0"

echo =====================================================================
echo    KHỞI CHẠY PIGSKIN AI STUDIO (DESKTOP APPLICATION - FLET)
echo =====================================================================
echo.

set PYTHON_BIN=python
if exist "%~dp0venv\Scripts\python.exe" set PYTHON_BIN="%~dp0venv\Scripts\python.exe"

cd PigSkinTech
%PYTHON_BIN% main.py
if errorlevel 1 (
    echo.
    echo [!] Gap loi khi khoi chay ung dung Desktop. Nhan phim bat ky de thoat...
    pause
)
