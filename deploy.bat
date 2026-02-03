@echo off
title Deploy Dental Lead Qualifier
cd /d "%~dp0"

echo.
echo ====================================
echo   DEPLOY: DENTAL LEAD QUALIFIER
echo ====================================
echo.
echo This will install everything needed to run
echo the Dental Lead Qualifier on this PC.
echo.
pause

echo.
echo [Step 1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Opening download page...
    start https://www.python.org/downloads/
    echo Please install Python and run this script again.
    pause
    exit /b 1
)
echo [OK] Python found
echo.

echo [Step 2/4] Installing Python packages...
pip install flask requests --user
if errorlevel 1 (
    echo [ERROR] Failed to install packages
    pause
    exit /b 1
)
echo [OK] Packages installed
echo.

echo [Step 3/4] Checking ngrok tunnel...
if exist ngrok.exe (
    echo [OK] ngrok.exe found locally
    goto :done_ngrok
)
where ngrok >nul 2>&1
if errorlevel 0 (
    echo [OK] ngrok installed in system
    goto :done_ngrok
)
echo Downloading ngrok...
powershell -Command "Invoke-WebRequest -Uri 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip' -OutFile 'ngrok.zip' -UseBasicParsing" >nul 2>&1
if exist ngrok.zip (
    powershell -Command "Expand-Archive -Path 'ngrok.zip' -DestinationPath '.' -Force" >nul 2>&1
    del ngrok.zip >nul 2>&1
    if exist ngrok.exe (
        echo [OK] ngrok downloaded
    ) else (
        echo [ERROR] ngrok download failed
        pause
        exit /b 1
    )
) else (
    echo [ERROR] Please download ngrok manually from https://ngrok.com/download
    pause
    exit /b 1
)
:done_ngrok
echo.

echo [Step 4/4] Testing server startup...
start /B python lead_qualifier_full.py > test_output.txt 2>&1
timeout /t 3 /nobreak >nul

python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5678/health', timeout=3).read().decode())" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Server test failed. Check test_output.txt
    type test_output.txt
) else (
    echo [OK] Server started successfully
    taskkill /F /IM python.exe /IM pythonw.exe >nul 2>&1
)
del test_output.txt >nul 2>&1
echo.

echo ====================================
echo   DEPLOYMENT COMPLETE!
echo ====================================
echo.
echo To run the application:
echo   Double-click: start.bat
echo.
echo Files in this folder:
echo   - start.bat       : Run the application
echo   - deploy.bat      : Install/update dependencies
echo   - lead_qualifier_full.py : Main application
echo.
echo The app will:
echo   1. Start local server on http://localhost:5678
echo   2. Create ngrok tunnel for public access
echo   3. Show your public URL (use this for Slack webhook)
echo.
pause
exit /b 0
