@echo off
title Dental Lead Qualifier - 24/7 Service
cd /d "%~dp0"

:LOOP
cls
echo ============================================================
echo   DENTAL LEAD QUALIFIER - 24/7 MODE
echo ============================================================
echo   Started: %date% %time%
echo.
echo   Press Ctrl+C to stop
echo ============================================================
echo.

python -u lead_qualifier_full.py

echo.
echo [%date% %time%] Server stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto LOOP
