@echo off
echo ============================================================
echo   UNINSTALL: Remove Auto-start
echo ============================================================
echo.
echo This will remove the Windows Scheduled Task.
echo The app will no longer start automatically.
echo.
pause

schtasks /delete /tn "DentalLeadQualifier" /f
if errorlevel 1 (
    echo.
    echo [ERROR] Task not found or already removed.
) else (
    echo.
    echo SUCCESS: Task removed.
)

echo.
pause
