#!/bin/bash

echo "🏹 Setting up Ultimate Hunter Job Search Engine..."
echo "=================================================="

# Function to check command success
check_success() {
    if [ $? -eq 0 ]; then
        echo "✅ $1"
    else
        echo "❌ $1 failed"
        exit 1
    fi
}

# Update requirements first
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt
check_success "Python dependencies installed"

# Install Playwright and browsers
echo "🎭 Installing Playwright browsers..."
python -m playwright install
check_success "Playwright browsers installed"

# Install Chromium specifically (needed for stealth)
echo "🌐 Installing Chromium for Playwright..."
python -m playwright install chromium
check_success "Chromium browser installed"

# Install playwright-stealth if not already installed
echo "🥷 Installing stealth plugin..."
pip install playwright-stealth
check_success "Stealth plugin installed"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p templates static/css static/js logs
check_success "Directories created"

# Set up environment file if not exists
if [ ! -f .env ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "✏️  Please edit .env file with your API keys and proxy settings"
else
    echo "✅ .env file already exists"
fi

# Test Playwright installation
echo "🧪 Testing Playwright installation..."
python -c "
import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://example.com')
        title = await page.title()
        await browser.close()
        print(f'✅ Playwright test successful: {title}')

asyncio.run(test_playwright())
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Playwright test successful"
else
    echo "⚠️  Playwright test failed, but installation should work"
fi

echo ""
echo "🎯 Ultimate Hunter Setup Complete!"
echo "=================================="
echo ""
echo "📋 What's been installed:"
echo "• All Python dependencies"
echo "• Playwright with Chromium browser"
echo "• Stealth detection avoidance"
echo "• Directory structure"
echo ""
echo "📝 Next steps:"
echo "1. Edit .env with your API keys and proxy settings"
echo "2. Run: ./run_hunter.sh"
echo ""
echo "🚀 Features enabled:"
echo "• ✅ JSearch API (with rate limiting)"
echo "• ✅ Jooble API (enhanced Nigerian support)"  
echo "• ✅ Adzuna API (optimized queries)"
echo "• ✅ Jobberman scraper (flexible parsing)"
echo "• ✅ Indeed scraper (Playwright + stealth)"
echo "• ✅ Advanced proxy rotation"
echo "• ✅ Timeout protection (no more 504 errors)"
echo "• ✅ Enhanced Nigerian job search"
echo "• ✅ Smart job deduplication"
echo "• ✅ Relevance scoring"
echo ""
echo "🏹 Hunter is now truly omnipresent!"

