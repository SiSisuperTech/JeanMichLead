@echo off
title Dental Lead Qualifier v1.0
cd /d "%~dp0"
cls

echo.
echo ============================================================
echo       DENTAL LEAD QUALIFIER - Professional Launcher
echo                    v1.0 - Feb 2026
echo ============================================================
echo.

echo [CLEANUP] Stopping old processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM ngrok.exe >nul 2>&1
taskkill /F /IM cloudflared.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo            OK
echo.

echo [PYTHON] Checking installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo            ERROR: Python not installed!
    echo            Get it from: https://python.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo            Python %%v
echo            OK
echo.

echo [PACKAGES] Checking dependencies...
python -c "import flask, requests" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo            Installing flask, requests...
    python -m pip install flask requests --user -q
)
echo            OK
echo.

echo [NGROK] Checking ngrok...
if exist ngrok.exe (
    echo            Using local ngrok.exe
    goto :ngrok_done
)
where ngrok >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo            Using system ngrok
    goto :ngrok_done
)
echo            Downloading ngrok...
powershell -Command "Invoke-WebRequest -Uri 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip' -OutFile 'ngrok.zip' -UseBasicParsing" >nul 2>&1
powershell -Command "Expand-Archive -Path 'ngrok.zip' -DestinationPath '.' -Force" >nul 2>&1
del ngrok.zip >nul 2>&1
if exist ngrok.exe (
    echo            Downloaded ngrok.exe
) else (
    echo            ERROR: Download failed!
    echo            Please download ngrok manually from: https://ngrok.com/download
    pause
    exit /b 1
)
:ngrok_done
echo            OK
echo.

echo ============================================================
echo  STARTING SERVICES
echo ============================================================
echo.

echo [1/2] Starting ngrok tunnel...
start "Ngrok Tunnel" ngrok.exe http 5678
timeout /t 3 /nobreak >nul
echo            Ngrok started - check the window for URL!
echo.

echo [2/2] Starting Python server (this window)...
echo.
echo ============================================================
echo  Press Ctrl+C to stop
echo ============================================================
echo.

python -u lead_qualifier_full.py

echo.
echo [STOP] Shutting down...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM ngrok.exe /FI "WINDOWTITLE eq Ngrok Tunnel*" >nul 2>&1
echo.
pause
