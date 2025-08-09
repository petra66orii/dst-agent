#!/bin/bash

# DST Trading Agent - Cloud Deployment Script
echo "🚀 Deploying DST Trading Agent to your cloud..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file template..."
    cat > .env << EOL
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Discord Configuration
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# SEC API Configuration
SEC_API_KEY=your_sec_api_key_here

# Alpha Vantage API Configuration
ALPHA_VANTAGE_KEY=your_alpha_vantage_api_key_here
EOL
    echo "⚠️  Please edit .env file with your actual API keys before running!"
    echo "   Then run: ./deploy_cloud.sh"
    exit 1
fi

# Build and start the containers
echo "🔨 Building Docker containers..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "✅ Deployment complete!"
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "📋 Useful Commands:"
echo "  View logs:           docker-compose logs -f"
echo "  Stop services:       docker-compose down"
echo "  Restart services:    docker-compose restart"
echo "  Update code:         git pull && docker-compose up -d --build"
echo ""
echo "🎯 Your trading bot is now running in the cloud!"
