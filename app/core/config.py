import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Keeps tests/imports working before dependencies are installed.
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# API configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", os.getenv("LLM_PROVIDER", "moonshot")).strip().lower()

MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
MOONSHOT_MODEL = os.getenv("MOONSHOT_MODEL", "kimi-k2.6")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

BROKER_MODE = os.getenv("BROKER_MODE", "simulation").strip().lower()
# Pionex Relay Config
PIONEX_RELAY_URL = os.getenv("PIONEX_RELAY_URL", "http://127.0.0.1:5000/webhook")
PIONEX_RELAY_ENABLED = os.getenv("PIONEX_RELAY_ENABLED", "false").strip().lower() == "true"
PIONEX_SIGNAL_BOT_UUID = os.getenv("PIONEX_SIGNAL_BOT_UUID", "")
PIONEX_RELAY_CONTRACTS = os.getenv("PIONEX_RELAY_CONTRACTS", "1")
PIONEX_RELAY_TIMEOUT_SECONDS = float(os.getenv("PIONEX_RELAY_TIMEOUT_SECONDS", "10"))

# Pionex Direct Config
PIONEX_DIRECT_ENABLED = os.getenv("PIONEX_DIRECT_ENABLED", "false").strip().lower() == "true"
PIONEX_DIRECT_LIVE_TRADING_ENABLED = os.getenv("PIONEX_DIRECT_LIVE_TRADING_ENABLED", "false").strip().lower() == "true"
PIONEX_API_KEY = os.getenv("PIONEX_API_KEY", "")
PIONEX_API_SECRET = os.getenv("PIONEX_API_SECRET", "")
PIONEX_ALLOWED_SYMBOLS = os.getenv("PIONEX_ALLOWED_SYMBOLS", "BTC_USDT,ETH_USDT,XAG_USDT_PERP")

# core config placeholder
MIN_RR_RATIO = 2.0
MAX_SPREAD = 15.0
MIN_CONFLUENCE_SCORE = 70.0
MAX_CRISIS_SCORE = 30.0
MAX_MC_DISPERSION = 5.0
MAX_DAILY_DRAWDOWN = 1000.0
MAX_TRADES_PER_DAY = 5
COOLDOWN_BARS = 3
