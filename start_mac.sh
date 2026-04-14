#!/bin/bash
echo ""
echo "================================"
echo " AgentCompany — First Time Setup"
echo "================================"
echo ""

if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv venv
fi

echo "[2/3] Installing dependencies..."
venv/bin/pip install -r requirements.txt

echo ""
echo "[3/3] Launching CEO Dashboard..."
echo " Open your browser at: http://localhost:8000"
echo ""
venv/bin/python main.py
