#!/bin/bash
set -e

echo "⬡ NEXUS — Setup"
echo "────────────────────────────────────────"

# 1. Python version check
python3 --version | grep -q "3.11" || echo "⚠️  Warning: NEXUS is tested on Python 3.11"

# 2. Install dependencies
echo "→ Installing Python dependencies..."
pip install -r requirements.txt

# 3. Create .env if missing
if [ ! -f .env ]; then
  echo "→ Creating .env file..."
  cat > .env << 'ENVEOF'
LLM_BACKEND=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
DB_PATH=nexus.db
ENVEOF
  echo "  .env created"
else
  echo "  .env already exists — skipping"
fi

# 4. Create outputs directory
mkdir -p outputs
echo "  outputs/ directory ready"

# 5. Check Ollama
if command -v ollama &> /dev/null; then
  echo "→ Ollama found"
  echo "→ Pulling llama3.2 model (skips if already present)..."
  ollama pull llama3.2
else
  echo "⚠️  Ollama not found."
  echo "   Install it from https://ollama.com then run: ollama pull llama3.2"
fi

echo ""
echo "✓ Setup complete."
echo ""
echo "To start NEXUS:"
echo "  Web UI → python3 app.py  then open http://127.0.0.1:8080"
echo "  CLI    → python run.py \"your research question\" --rounds 3 --hypotheses 5 --papers 5"
