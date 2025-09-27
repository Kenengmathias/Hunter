#!/bin/bash

# Hunter Job Search Setup Script

echo "🏹 Setting up Hunter Job Search Engine..."

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p templates static logs

# Install Python dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
python -m playwright install

# Copy environment file
if [ ! -f .env ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "✏️  Please edit .env file with your API keys and proxy settings"
else
    echo "✅ .env file already exists"
fi

# Create basic templates directory structure
echo "🎨 Creating template structure..."
mkdir -p templates static/css static/js

# Set permissions
chmod +x setup.sh

echo "🎯 Hunter setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Add your Webshare proxy credentials to .env"
echo "3. Create templates/index.html (we'll do this next)"
echo "4. Run: python app.py"
echo ""
echo "🚀 Ready to hunt for jobs!"
