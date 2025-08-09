@echo off
REM Archived: Persistent scheduler loop. Use GitHub Actions for scheduling now.
cd /d "c:\Users\Petra\.vscode\vscode_projects\dst-agent"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python src\scheduler.py
