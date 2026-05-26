@echo off
title Nara — Starting All Services
echo ===========================================
echo   Nara — Membuka 4 Terminal Service
echo ===========================================
echo.

cd /d "%~dp0"

echo [1/4] Server API (port 8000)...
start "SERVER" cmd /k python -m uvicorn server:app --host 0.0.0.0 --port 8000

timeout /t 1 /nobreak >nul

echo [2/4] WhatsApp Handler (port 3001)...
start "WA_HANDLER" cmd /k python wa_handler.py

timeout /t 1 /nobreak >nul

echo [3/4] WhatsApp Bridge (port 3000)...
start "BRIDGE" cmd /k cd whatsapp-bridge ^&^& node bridge.js

timeout /t 1 /nobreak >nul

echo [4/4] Telegram Bot...
start "TELEGRAM" cmd /k python telegram_bot.py

echo.
echo ===========================================
echo   ✅ Semua service sudah dibuka!
echo   Tutup aja jendela ini.
echo ===========================================
timeout /t 3 /nobreak >nul
