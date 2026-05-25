import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Keeps tests/imports working before dependencies are installed.
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _as_optional_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _as_csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip().upper() for part in value.split(",") if part.strip()]


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

# Broker mode selection
BROKER_MODE = os.getenv("BROKER_MODE", "simulation").strip().lower()

# Relay broker configuration
PIONEX_RELAY_URL = os.getenv("PIONEX_RELAY_URL", "http://127.0.0.1:5000/webhook")
PIONEX_RELAY_ENABLED = _as_bool(os.getenv("PIONEX_RELAY_ENABLED"), False)
PIONEX_SIGNAL_BOT_UUID = os.getenv("PIONEX_SIGNAL_BOT_UUID", "")
PIONEX_RELAY_CONTRACTS = os.getenv("PIONEX_RELAY_CONTRACTS", "1")
PIONEX_RELAY_TIMEOUT_SECONDS = _as_float(os.getenv("PIONEX_RELAY_TIMEOUT_SECONDS"), 10.0)

# Direct Pionex broker (native execution)
PIONEX_DIRECT_ENABLED = _as_bool(os.getenv("PIONEX_DIRECT_ENABLED"), False)
PIONEX_DIRECT_LIVE_TRADING_ENABLED = _as_bool(os.getenv("PIONEX_DIRECT_LIVE_TRADING_ENABLED"), False)
PIONEX_API_KEY = os.getenv("PIONEX_API_KEY", "")
PIONEX_API_SECRET = os.getenv("PIONEX_API_SECRET", "")
PIONEX_DIRECT_BASE_URL = os.getenv("PIONEX_DIRECT_BASE_URL", "https://api.pionex.com").strip()
PIONEX_DIRECT_TIMEOUT_SECONDS = _as_float(os.getenv("PIONEX_DIRECT_TIMEOUT_SECONDS"), 10.0)
PIONEX_ALLOWED_SYMBOLS = _as_csv_list(os.getenv("PIONEX_ALLOWED_SYMBOLS"))
PIONEX_DIRECT_DEFAULT_SPOT_SYMBOL = os.getenv("PIONEX_DIRECT_DEFAULT_SPOT_SYMBOL", "BTC_USDT").strip().upper()
PIONEX_DIRECT_DEFAULT_FUTURES_SYMBOL = os.getenv("PIONEX_DIRECT_DEFAULT_FUTURES_SYMBOL", "BTC_USDT_PERP").strip().upper()
PIONEX_DIRECT_FUTURES_ENABLED = _as_bool(os.getenv("PIONEX_DIRECT_FUTURES_ENABLED"), True)
PIONEX_DIRECT_FUTURES_MODE = os.getenv("PIONEX_DIRECT_FUTURES_MODE", "mode1").strip().lower()  # mode1|mode3
PIONEX_DIRECT_ALLOW_PAYLOAD_LEVERAGE = _as_bool(os.getenv("PIONEX_DIRECT_ALLOW_PAYLOAD_LEVERAGE"), False)

# Kelly sizing controls
KELLY_DEPLOY_MODE = os.getenv("KELLY_DEPLOY_MODE", "half").strip().lower()  # half|full|fixed
KELLY_LOOKBACK_TRADES = _as_int(os.getenv("KELLY_LOOKBACK_TRADES"), 50)
KELLY_MIN_TRADES = _as_int(os.getenv("KELLY_MIN_TRADES"), 20)
KELLY_FIXED_RISK_PCT = _as_float(os.getenv("KELLY_FIXED_RISK_PCT"), 1.0)
KELLY_MIN_RISK_PCT = _as_float(os.getenv("KELLY_MIN_RISK_PCT"), 0.2)
KELLY_MAX_RISK_PCT = _as_float(os.getenv("KELLY_MAX_RISK_PCT"), 2.0)
KELLY_PAYOFF_BUFFER = _as_float(os.getenv("KELLY_PAYOFF_BUFFER"), 0.0)

# Direct execution order size guards
PIONEX_DIRECT_MAX_ORDER_USDT = _as_float(os.getenv("PIONEX_DIRECT_MAX_ORDER_USDT"), 200.0)
PIONEX_DIRECT_MIN_ORDER_USDT = _as_float(os.getenv("PIONEX_DIRECT_MIN_ORDER_USDT"), 5.0)
PIONEX_DIRECT_MAX_BASE_SIZE = _as_float(os.getenv("PIONEX_DIRECT_MAX_BASE_SIZE"), 10.0)
PIONEX_DIRECT_MIN_BASE_SIZE = _as_float(os.getenv("PIONEX_DIRECT_MIN_BASE_SIZE"), 0.0001)

# AI availability policy for live-capable modes
AI_FAILURE_POLICY = os.getenv("AI_FAILURE_POLICY", "reject_live").strip().lower()  # reject_live|allow_live
AI_TELEGRAM_ADVISORS_ENABLED = _as_bool(os.getenv("AI_TELEGRAM_ADVISORS_ENABLED"), False)
AI_TELEGRAM_ADVISOR_TIMEOUT_SECONDS = _as_float(os.getenv("AI_TELEGRAM_ADVISOR_TIMEOUT_SECONDS"), 20.0)

# Deterministic War Room order-management controls
WAR_ROOM_ENABLED = _as_bool(os.getenv("WAR_ROOM_ENABLED"), True)
WAR_ROOM_CHOP_STANDBY_THRESHOLD = _as_float(os.getenv("WAR_ROOM_CHOP_STANDBY_THRESHOLD"), 61.8)
WAR_ROOM_HURST_HAZARD_THRESHOLD = _as_float(os.getenv("WAR_ROOM_HURST_HAZARD_THRESHOLD"), 0.45)
WAR_ROOM_HARD_KILL_DRAWDOWN_PCT = _as_float(os.getenv("WAR_ROOM_HARD_KILL_DRAWDOWN_PCT"), 25.0)
WAR_ROOM_ORANGE_MAX_RISK_PCT = _as_float(os.getenv("WAR_ROOM_ORANGE_MAX_RISK_PCT"), 1.0)
WAR_ROOM_AI_MIN_CONFIDENCE = _as_float(os.getenv("WAR_ROOM_AI_MIN_CONFIDENCE"), 0.55)
WAR_ROOM_PENDING_ORDER_MAX_AGE_SECONDS = _as_float(os.getenv("WAR_ROOM_PENDING_ORDER_MAX_AGE_SECONDS"), 300.0)
WAR_ROOM_VIP_CONFLUENCE_SCORE = _as_float(os.getenv("WAR_ROOM_VIP_CONFLUENCE_SCORE"), 85.0)
WAR_ROOM_VIP_RELATIVE_VOLUME = _as_float(os.getenv("WAR_ROOM_VIP_RELATIVE_VOLUME"), 1.5)
WAR_ROOM_VIP_MAX_CRISIS_SCORE = _as_float(os.getenv("WAR_ROOM_VIP_MAX_CRISIS_SCORE"), 15.0)
WAR_ROOM_VIP_MAX_MC_DISPERSION = _as_float(os.getenv("WAR_ROOM_VIP_MAX_MC_DISPERSION"), 2.5)

# Webhook authentication
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Offline/backtest signal generator controls
SIGNAL_MIN_CONFLUENCE_OVERRIDE = _as_optional_float(os.getenv("SIGNAL_MIN_CONFLUENCE_OVERRIDE"))

# Telegram notifier
TELEGRAM_NOTIFICATIONS_ENABLED = _as_bool(os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED"), False)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# GLINT broker configuration
GLINT_ENABLED = _as_bool(os.getenv("GLINT_ENABLED"), False)
GLINT_LIVE_TRADING_ENABLED = _as_bool(os.getenv("GLINT_LIVE_TRADING_ENABLED"), False)
GLINT_TELEGRAM_CHAT_ID = os.getenv("GLINT_TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
GLINT_BOT_USERNAME = os.getenv("GLINT_BOT_USERNAME", "")

# Manus advisor configuration (separate Telegram chat)
MANUS_ENABLED = _as_bool(os.getenv("MANUS_ENABLED"), False)
MANUS_TELEGRAM_CHAT_ID = os.getenv("MANUS_TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
MANUS_BOT_USERNAME = os.getenv("MANUS_BOT_USERNAME", "")

# Autonomous Loop configuration
AUTONOMOUS_LOOP_ENABLED = _as_bool(os.getenv("AUTONOMOUS_LOOP_ENABLED"), False)
AUTONOMOUS_LOOP_AUTO_START = _as_bool(os.getenv("AUTONOMOUS_LOOP_AUTO_START"), False)
AUTONOMOUS_LOOP_POLL_INTERVAL_SECONDS = _as_float(os.getenv("AUTONOMOUS_LOOP_POLL_INTERVAL_SECONDS"), 60.0)
AUTONOMOUS_LOOP_MAX_ERRORS_5MIN = _as_int(os.getenv("AUTONOMOUS_LOOP_MAX_ERRORS_5MIN"), 20)
AUTONOMOUS_LOOP_PAUSE_ON_ERROR_COUNT = _as_int(os.getenv("AUTONOMOUS_LOOP_PAUSE_ON_ERROR_COUNT"), 5)
AUTONOMOUS_LOOP_ERROR_PAUSE_SECONDS = _as_float(os.getenv("AUTONOMOUS_LOOP_ERROR_PAUSE_SECONDS"), 60.0)
AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED = _as_bool(os.getenv("AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED"), True)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/data/trading.db")

# News Impact configuration
NEWS_IMPACT_ENABLED = _as_bool(os.getenv("NEWS_IMPACT_ENABLED"), True)
NEWS_IMPACT_MAX_AGE_HOURS = _as_float(os.getenv("NEWS_IMPACT_MAX_AGE_HOURS"), 24.0)
NEWS_IMPACT_MIN_RELEVANCE = _as_float(os.getenv("NEWS_IMPACT_MIN_RELEVANCE"), 0.3)
NEWS_IMPACT_SENTIMENT_THRESHOLD = _as_float(os.getenv("NEWS_IMPACT_SENTIMENT_THRESHOLD"), 0.5)
NEWS_IMPACT_URGENCY_THRESHOLD = _as_float(os.getenv("NEWS_IMPACT_URGENCY_THRESHOLD"), 0.7)
NEWS_POLL_INTERVAL_MINUTES = _as_float(os.getenv("NEWS_POLL_INTERVAL_MINUTES"), 15.0)

# Deterministic risk-gate defaults
MIN_RR_RATIO = 2.0
MAX_SPREAD = 15.0
MIN_CONFLUENCE_SCORE = 70.0
MAX_CRISIS_SCORE = 30.0
MAX_MC_DISPERSION = 5.0
MAX_DAILY_DRAWDOWN = _as_float(os.getenv("MAX_DAILY_DRAWDOWN"), 5.0)
MAX_TRADES_PER_DAY = 5
COOLDOWN_BARS = 3
