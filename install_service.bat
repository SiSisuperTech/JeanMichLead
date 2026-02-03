@echo off
echo ============================================================
echo   INSTALL: Auto-start on Windows boot
echo ============================================================
echo.
echo This will create a Windows Scheduled Task to
echo automatically start the Dental Lead Qualifier
echo when Windows starts.
echo.
pause

:: Get full path of the script
set "SCRIPT_PATH=%~dp0start_service.bat"
set "SCRIPT_PATH=%SCRIPT_PATH:\=/%"

:: Create the scheduled task
schtasks /create /tn "DentalLeadQualifier" /tr "\"%SCRIPT_PATH%\"" /sc onlogon /rl highest /f
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create scheduled task.
    echo         Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SUCCESS!
echo ============================================================
echo.
echo Scheduled task created: DentalLeadQualifier
echo.
echo The app will now:
echo   - Start automatically when you log in to Windows
echo   - Restart automatically if it crashes
echo.
echo To remove later, run: schtasks /delete /tn DentalLeadQualifier
echo.
echo Starting now...
echo ============================================================
echo.

start start_service.bat
