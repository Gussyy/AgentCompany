#!/bin/bash
# AgentCompany — first-time setup
set -e

echo "🔧 Creating virtual environment..."
python3 -m venv venv

echo "📦 Installing dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the CEO dashboard:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Or to run a quick CLI test:"
echo "  source venv/bin/activate"
echo "  python main.py run --industry 'productivity tools'"
