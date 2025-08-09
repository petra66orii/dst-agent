@echo off
title DST Trading Agent - Quick Setup
echo 🚀 DST Trading Agent - Quick Setup
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo    Please install Python 3.12+ from https://python.org
    pause
    exit /b 1
)

echo ✅ Python is installed
python --version

REM Check if we're in the right directory
if not exist "src\main.py" (
    echo ❌ Please run this script from the dst-agent root directory
    pause
    exit /b 1
)

echo ✅ In correct directory

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install requirements
echo 📚 Installing Python packages...
pip install -r requirements.txt

REM Check if config file exists
if not exist "config\config.py" (
    echo 📝 Creating config template...
    if not exist "config" mkdir config
    echo # DST Trading Agent Configuration > config\config.py
    echo. >> config\config.py
    echo # OpenAI API Key >> config\config.py
    echo OPENAI_API_KEY = "your_openai_api_key_here" >> config\config.py
    echo. >> config\config.py
    echo # Discord Configuration >> config\config.py
    echo DISCORD_WEBHOOK_URL = "your_discord_webhook_url_here" >> config\config.py
    echo DISCORD_BOT_TOKEN = "your_discord_bot_token_here" >> config\config.py
    echo. >> config\config.py
    echo # SEC API Key >> config\config.py
    echo SEC_API_KEY = "your_sec_api_key_here" >> config\config.py
    echo. >> config\config.py
    echo # Alpha Vantage API Key >> config\config.py
    echo ALPHA_VANTAGE_API_KEY = "your_alpha_vantage_api_key_here" >> config\config.py
    echo.
    echo ⚠️  Please edit config\config.py with your actual API keys!
    echo    Required: OpenAI, Discord Webhook, SEC API
    echo    Optional: Discord Bot Token, Alpha Vantage
)

echo.
echo ✅ Setup Complete!
echo.
echo 📋 Next Steps:
echo   1. Edit config\config.py with your API keys
echo   2. Run a component:
echo      • Daily Analysis:  python src\main.py
echo      • Discord Bot:     python src\discord_bot.py
echo      • Scheduler:       python src\scheduler.py
echo   3. Or use quick scripts:
echo      • scripts\start_discord_bot.bat
echo      • scripts\start_persistent_scheduler.bat
echo.
echo 📖 See README.md for detailed documentation
echo.
pause
