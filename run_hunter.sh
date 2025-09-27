#!/bin/bash

# Hunter Job Search Engine - Startup Script

echo "🏹 Starting Hunter Job Search Engine..."
echo "=================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys:"
    echo "cp .env.example .env"
    echo "nano .env"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo "💡 Creating Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment found"
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        source .venv/bin/activate
    fi
fi

# Install requirements if needed
echo "📦 Checking dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

# Install Playwright browsers if needed
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
    echo "🌐 Installing Playwright browsers..."
    python -m playwright install
fi

# Check if templates exist
if [ ! -f "templates/index.html" ]; then
    echo "❌ Error: Templates not found!"
    echo "Please run the template creation script first:"
    echo "./create_templates.sh"
    exit 1
fi

echo ""
echo "🔧 Configuration Check:"
echo "======================"

# Check API keys
source .env
missing_keys=()

if [ -z "$JOOBLE_API_KEY" ]; then
    missing_keys+=("JOOBLE_API_KEY")
fi

if [ -z "$ADZUNA_APP_ID" ] || [ -z "$ADZUNA_APP_KEY" ]; then
    missing_keys+=("ADZUNA_APP_ID/ADZUNA_APP_KEY")
fi

if [ -z "$JSEARCH_API_KEY" ]; then
    missing_keys+=("JSEARCH_API_KEY")
fi

if [ ${#missing_keys[@]} -gt 0 ]; then
    echo "⚠️  Warning: Missing API keys: ${missing_keys[*]}"
    echo "   Hunter will still work with available APIs and web scraping"
else
    echo "✅ All API keys configured"
fi

if [ -z "$PROXY_LIST" ]; then
    echo "⚠️  Warning: No proxy list configured"
    echo "   Web scraping may be limited without proxies"
else
    echo "✅ Proxy list configured"
fi

echo ""
echo "🚀 Starting Hunter Job Search Engine..."
echo "======================================"
echo "Access your job search engine at: http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

# Start the application
python app.py

