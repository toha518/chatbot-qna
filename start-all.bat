@echo off
title Nara — Starting All Services
echo ===========================================
echo   Nara — Membuka 5 Terminal Service
echo ===========================================
echo.

cd /d "%~dp0"

echo [1/5] Server API (port 8000)...
start "SERVER" cmd /k python -m uvicorn server:app --host 0.0.0.0 --port 8000

timeout /t 1 /nobreak >nul

echo [2/5] Dashboard (port 8001)...
start "DASHBOARD" cmd /k python dashboard.py

timeout /t 1 /nobreak >nul

echo [3/5] WhatsApp Handler (port 3001)...
start "WA_HANDLER" cmd /k python wa_handler.py

timeout /t 1 /nobreak >nul

echo [4/5] WhatsApp Bridge (port 3000)...
start "BRIDGE" cmd /k cd whatsapp-bridge ^&^& node bridge.js

timeout /t 1 /nobreak >nul

echo [5/5] Telegram Bot...
start "TELEGRAM" cmd /k python telegram_bot.py

:: Tunggu semua service siap, lalu buka dashboard
timeout /t 5 /nobreak >nul
start http://localhost:8001

echo.
echo ===========================================
echo   ✅ Semua service sudah dibuka!
echo   
echo   📊 Dashboard: http://localhost:8001
echo   🔧 API:       http://localhost:8000
echo   📱 WA:        http://localhost:3001
echo ===========================================
timeout /t 3 /nobreak >nul
