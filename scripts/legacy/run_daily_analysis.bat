@echo off
REM Archived: Local daily run script. GitHub Actions now handles scheduling.
REM Original kept for future self-hosting.

cd /d "c:\Users\Petra\.vscode\vscode_projects\dst-agent"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python main.py > daily_run_%date:~-4,4%-%date:~-10,2%-%date:~-7,2%.log 2>&1
