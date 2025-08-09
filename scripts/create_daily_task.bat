@echo off
echo Creating Daily Trading Analysis Task...
echo.

REM Create the scheduled task using schtasks
schtasks /create ^
    /tn "Daily-Trading-Analysis" ^
    /tr "\"c:\Users\Petra\.vscode\vscode_projects\dst-agent\run_daily_analysis.bat\"" ^
    /sc daily ^
    /st 13:00 ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo ✅ Task created successfully!
    echo.
    echo Task Details:
    echo - Name: Daily-Trading-Analysis
    echo - Schedule: Daily at 1:00 PM
    echo - Command: run_daily_analysis.bat
    echo.
    echo To test manually: schtasks /run /tn "Daily-Trading-Analysis"
    echo To delete: schtasks /delete /tn "Daily-Trading-Analysis" /f
) else (
    echo ❌ Failed to create task. You may need to run as Administrator.
)

echo.
pause
