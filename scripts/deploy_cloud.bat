@echo off
title DST Trading Agent - Cloud Deployment
echo 🚀 Deploying DST Trading Agent to your cloud...
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    echo    Download from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not available. Please install Docker Desktop.
    pause
    exit /b 1
)

REM Create environment file if it doesn't exist
if not exist .env (
    echo 📝 Creating .env file template...
    echo # OpenAI API Configuration > .env
    echo OPENAI_API_KEY=your_openai_api_key_here >> .env
    echo. >> .env
    echo # Discord Configuration >> .env
    echo DISCORD_WEBHOOK_URL=your_discord_webhook_url_here >> .env
    echo DISCORD_BOT_TOKEN=your_discord_bot_token_here >> .env
    echo. >> .env
    echo # SEC API Configuration >> .env
    echo SEC_API_KEY=your_sec_api_key_here >> .env
    echo. >> .env
    echo # Alpha Vantage API Configuration >> .env
    echo ALPHA_VANTAGE_KEY=your_alpha_vantage_api_key_here >> .env
    echo.
    echo ⚠️  Please edit .env file with your actual API keys before running!
    echo    Then run: deploy_cloud.bat
    pause
    exit /b 1
)

REM Build and start the containers
echo 🔨 Building Docker containers...
cd /d "c:\Users\Petra\.vscode\vscode_projects\dst-agent\deployment"
docker-compose build

echo 🚀 Starting services...
docker-compose up -d

echo ✅ Deployment complete!
echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo 📋 Useful Commands:
echo   View logs:           docker-compose logs -f
echo   Stop services:       docker-compose down
echo   Restart services:    docker-compose restart
echo   Update code:         docker-compose up -d --build
echo.
echo 🎯 Your trading bot is now running in the cloud!
pause
