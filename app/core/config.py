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
AI_REVIEW_ENGINE = os.getenv("AI_REVIEW_ENGINE", "gem10_native").strip().lower()

MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
MOONSHOT_MODEL = os.getenv("MOONSHOT_MODEL", "kimi-k2.6")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "local-model")

# Per-scout AI provider overrides
AI_PROVIDER_TECHNICAL = os.getenv("AI_PROVIDER_TECHNICAL", "").strip().lower()
AI_PROVIDER_SENTIMENT = os.getenv("AI_PROVIDER_SENTIMENT", "").strip().lower()
AI_PROVIDER_RISK = os.getenv("AI_PROVIDER_RISK", "").strip().lower()
AI_PROVIDER_MACRO = os.getenv("AI_PROVIDER_MACRO", "").strip().lower()
AI_PROVIDER_EXECUTION = os.getenv("AI_PROVIDER_EXECUTION", "").strip().lower()
AI_PROVIDER_CORRELATION = os.getenv("AI_PROVIDER_CORRELATION", "").strip().lower()

# Per-scout model overrides
AI_MODEL_TECHNICAL = os.getenv("AI_MODEL_TECHNICAL", "").strip()
AI_MODEL_SENTIMENT = os.getenv("AI_MODEL_SENTIMENT", "").strip()
AI_MODEL_RISK = os.getenv("AI_MODEL_RISK", "").strip()
AI_MODEL_MACRO = os.getenv("AI_MODEL_MACRO", "").strip()
AI_MODEL_EXECUTION = os.getenv("AI_MODEL_EXECUTION", "").strip()
AI_MODEL_CORRELATION = os.getenv("AI_MODEL_CORRELATION", "").strip()


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

# cTrader Open API broker
CTRADER_ENABLED = _as_bool(os.getenv("CTRADER_ENABLED"), False)
CTRADER_LIVE_TRADING_ENABLED = _as_bool(os.getenv("CTRADER_LIVE_TRADING_ENABLED"), False)
CTRADER_CLIENT_ID = os.getenv("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN", "")
CTRADER_ACCOUNT_ID = _as_int(os.getenv("CTRADER_ACCOUNT_ID"), 0)
CTRADER_HOST = os.getenv("CTRADER_HOST", "demo.ctraderapi.com").strip()
CTRADER_PORT = _as_int(os.getenv("CTRADER_PORT"), 5035)
CTRADER_SYMBOL_MAP_PATH = os.getenv("CTRADER_SYMBOL_MAP_PATH", "ctrader_symbols.json")

# cTrader FIX API (alternative to Open API)
CTRADER_FIX_ENABLED = _as_bool(os.getenv("CTRADER_FIX_ENABLED"), False)
CTRADER_FIX_LIVE_TRADING_ENABLED = _as_bool(os.getenv("CTRADER_FIX_LIVE_TRADING_ENABLED"), False)
CTRADER_FIX_HOST = os.getenv("CTRADER_FIX_HOST", "demo-uk-eqx-01.p.c-trader.com").strip()
CTRADER_FIX_PORT = _as_int(os.getenv("CTRADER_FIX_PORT"), 5212)
CTRADER_FIX_SENDER_COMP_ID = os.getenv("CTRADER_FIX_SENDER_COMP_ID", "")
CTRADER_FIX_TARGET_COMP_ID = os.getenv("CTRADER_FIX_TARGET_COMP_ID", "cServer")
CTRADER_FIX_PASSWORD = os.getenv("CTRADER_FIX_PASSWORD", "")
CTRADER_FIX_SENDER_SUB_ID = os.getenv("CTRADER_FIX_SENDER_SUB_ID", "TRADE")

# Kraken broker configuration
KRAKEN_ENABLED = _as_bool(os.getenv("KRAKEN_ENABLED"), False)
KRAKEN_LIVE_TRADING_ENABLED = _as_bool(os.getenv("KRAKEN_LIVE_TRADING_ENABLED"), False)
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")
KRAKEN_TIMEOUT_SECONDS = _as_float(os.getenv("KRAKEN_TIMEOUT_SECONDS"), 20.0)
KRAKEN_DEMO_MODE = _as_bool(os.getenv("KRAKEN_DEMO_MODE"), True)
KRAKEN_SPOT_ONLY = _as_bool(os.getenv("KRAKEN_SPOT_ONLY"), True)
KRAKEN_MAX_ORDER_USD = _as_float(os.getenv("KRAKEN_MAX_ORDER_USD"), 100.0)
KRAKEN_MIN_ORDER_USD = _as_float(os.getenv("KRAKEN_MIN_ORDER_USD"), 10.0)

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

# AI Training Academy loop configuration
TRAINING_LOOP_ENABLED = _as_bool(os.getenv("TRAINING_LOOP_ENABLED"), True)
TRAINING_LOOP_AUTO_START = _as_bool(os.getenv("TRAINING_LOOP_AUTO_START"), False)
TRAINING_LOOP_NIGHT_MODE = _as_bool(os.getenv("TRAINING_LOOP_NIGHT_MODE"), True)
TRAINING_LOOP_NIGHT_START = os.getenv("TRAINING_LOOP_NIGHT_START", "22:00").strip()
TRAINING_LOOP_NIGHT_END = os.getenv("TRAINING_LOOP_NIGHT_END", "06:00").strip()
TRAINING_LOOP_DRILLS_PER_HOUR = _as_float(os.getenv("TRAINING_LOOP_DRILLS_PER_HOUR"), 12.0)

# Price Poller / Position Monitor configuration
PRICE_POLLER_INTERVAL_SECONDS = _as_float(os.getenv("PRICE_POLLER_INTERVAL_SECONDS"), 10.0)
POSITION_MAX_HOLD_MINUTES = _as_float(os.getenv("POSITION_MAX_HOLD_MINUTES"), 240.0)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/data/trading.db")

# News Impact configuration
NEWS_IMPACT_ENABLED = _as_bool(os.getenv("NEWS_IMPACT_ENABLED"), True)
NEWS_IMPACT_MAX_AGE_HOURS = _as_float(os.getenv("NEWS_IMPACT_MAX_AGE_HOURS"), 24.0)
MOONSHOT_BASE_URL = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
MOONSHOT_MODEL = os.getenv("MOONSHOT_MODEL", "kimi-k2.6")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "local-model")

# Per-scout AI provider overrides
AI_PROVIDER_TECHNICAL = os.getenv("AI_PROVIDER_TECHNICAL", "").strip().lower()
AI_PROVIDER_SENTIMENT = os.getenv("AI_PROVIDER_SENTIMENT", "").strip().lower()
AI_PROVIDER_RISK = os.getenv("AI_PROVIDER_RISK", "").strip().lower()
AI_PROVIDER_MACRO = os.getenv("AI_PROVIDER_MACRO", "").strip().lower()
AI_PROVIDER_EXECUTION = os.getenv("AI_PROVIDER_EXECUTION", "").strip().lower()
AI_PROVIDER_CORRELATION = os.getenv("AI_PROVIDER_CORRELATION", "").strip().lower()

# Per-scout model overrides
AI_MODEL_TECHNICAL = os.getenv("AI_MODEL_TECHNICAL", "").strip()
AI_MODEL_SENTIMENT = os.getenv("AI_MODEL_SENTIMENT", "").strip()
AI_MODEL_RISK = os.getenv("AI_MODEL_RISK", "").strip()
AI_MODEL_MACRO = os.getenv("AI_MODEL_MACRO", "").strip()
AI_MODEL_EXECUTION = os.getenv("AI_MODEL_EXECUTION", "").strip()
AI_MODEL_CORRELATION = os.getenv("AI_MODEL_CORRELATION", "").strip()


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

# cTrader Open API broker
CTRADER_ENABLED = _as_bool(os.getenv("CTRADER_ENABLED"), False)
CTRADER_LIVE_TRADING_ENABLED = _as_bool(os.getenv("CTRADER_LIVE_TRADING_ENABLED"), False)
CTRADER_CLIENT_ID = os.getenv("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN", "")
CTRADER_ACCOUNT_ID = _as_int(os.getenv("CTRADER_ACCOUNT_ID"), 0)
CTRADER_HOST = os.getenv("CTRADER_HOST", "demo.ctraderapi.com").strip()
CTRADER_PORT = _as_int(os.getenv("CTRADER_PORT"), 5035)
CTRADER_SYMBOL_MAP_PATH = os.getenv("CTRADER_SYMBOL_MAP_PATH", "ctrader_symbols.json")

# cTrader FIX API (alternative to Open API)
CTRADER_FIX_ENABLED = _as_bool(os.getenv("CTRADER_FIX_ENABLED"), False)
CTRADER_FIX_LIVE_TRADING_ENABLED = _as_bool(os.getenv("CTRADER_FIX_LIVE_TRADING_ENABLED"), False)
CTRADER_FIX_HOST = os.getenv("CTRADER_FIX_HOST", "demo-uk-eqx-01.p.c-trader.com").strip()
CTRADER_FIX_PORT = _as_int(os.getenv("CTRADER_FIX_PORT"), 5212)
CTRADER_FIX_SENDER_COMP_ID = os.getenv("CTRADER_FIX_SENDER_COMP_ID", "")
CTRADER_FIX_TARGET_COMP_ID = os.getenv("CTRADER_FIX_TARGET_COMP_ID", "cServer")
CTRADER_FIX_PASSWORD = os.getenv("CTRADER_FIX_PASSWORD", "")
CTRADER_FIX_SENDER_SUB_ID = os.getenv("CTRADER_FIX_SENDER_SUB_ID", "TRADE")

# Kraken broker configuration
KRAKEN_ENABLED = _as_bool(os.getenv("KRAKEN_ENABLED"), False)
KRAKEN_LIVE_TRADING_ENABLED = _as_bool(os.getenv("KRAKEN_LIVE_TRADING_ENABLED"), False)
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")
KRAKEN_TIMEOUT_SECONDS = _as_float(os.getenv("KRAKEN_TIMEOUT_SECONDS"), 20.0)
KRAKEN_DEMO_MODE = _as_bool(os.getenv("KRAKEN_DEMO_MODE"), True)
KRAKEN_SPOT_ONLY = _as_bool(os.getenv("KRAKEN_SPOT_ONLY"), True)
KRAKEN_MAX_ORDER_USD = _as_float(os.getenv("KRAKEN_MAX_ORDER_USD"), 100.0)
KRAKEN_MIN_ORDER_USD = _as_float(os.getenv("KRAKEN_MIN_ORDER_USD"), 10.0)

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

# AI Training Academy loop configuration
TRAINING_LOOP_ENABLED = _as_bool(os.getenv("TRAINING_LOOP_ENABLED"), True)
TRAINING_LOOP_AUTO_START = _as_bool(os.getenv("TRAINING_LOOP_AUTO_START"), False)
TRAINING_LOOP_NIGHT_MODE = _as_bool(os.getenv("TRAINING_LOOP_NIGHT_MODE"), True)
TRAINING_LOOP_NIGHT_START = os.getenv("TRAINING_LOOP_NIGHT_START", "22:00").strip()
TRAINING_LOOP_NIGHT_END = os.getenv("TRAINING_LOOP_NIGHT_END", "06:00").strip()
TRAINING_LOOP_DRILLS_PER_HOUR = _as_float(os.getenv("TRAINING_LOOP_DRILLS_PER_HOUR"), 12.0)

# Academy PPO meta-policy controls. Training/export run in a separate Python 3.11 RL venv.
ACADEMY_POLICY_MODE = os.getenv("ACADEMY_POLICY_MODE", "shadow").strip().lower()  # shadow|heuristic|ppo
if ACADEMY_POLICY_MODE not in {"shadow", "heuristic", "ppo"}:
    ACADEMY_POLICY_MODE = "shadow"
ACADEMY_POLICY_BACKEND = os.getenv("ACADEMY_POLICY_BACKEND", "heuristic").strip().lower()  # heuristic|torch|onnx
if ACADEMY_POLICY_BACKEND not in {"heuristic", "torch", "onnx"}:
    ACADEMY_POLICY_BACKEND = "heuristic"
ACADEMY_POLICY_MODEL_DIR = os.getenv(
    "ACADEMY_POLICY_MODEL_DIR",
    "data/academy_policy/models/active",
).strip()
ACADEMY_POLICY_CYCLE_DECISIONS = _as_int(os.getenv("ACADEMY_POLICY_CYCLE_DECISIONS"), 16)
ACADEMY_POLICY_MIN_EVAL_LIFT = _as_float(os.getenv("ACADEMY_POLICY_MIN_EVAL_LIFT"), 0.05)

# Price Poller / Position Monitor configuration
PRICE_POLLER_INTERVAL_SECONDS = _as_float(os.getenv("PRICE_POLLER_INTERVAL_SECONDS"), 10.0)
POSITION_MAX_HOLD_MINUTES = _as_float(os.getenv("POSITION_MAX_HOLD_MINUTES"), 240.0)

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
MIN_RR_RATIO = _as_float(os.getenv("MIN_RR_RATIO"), 2.0)
MAX_SPREAD = _as_float(os.getenv("MAX_SPREAD"), 15.0)
MIN_CONFLUENCE_SCORE = _as_float(os.getenv("MIN_CONFLUENCE_SCORE"), 70.0)
MAX_CRISIS_SCORE = _as_float(os.getenv("MAX_CRISIS_SCORE"), 30.0)
MAX_MC_DISPERSION = _as_float(os.getenv("MAX_MC_DISPERSION"), 5.0)
MAX_DAILY_DRAWDOWN = _as_float(os.getenv("MAX_DAILY_DRAWDOWN"), 5.0)
MAX_TRADES_PER_DAY = _as_int(os.getenv("MAX_TRADES_PER_DAY"), 5)
COOLDOWN_BARS = _as_int(os.getenv("COOLDOWN_BARS"), 3)
REGIME_ALLOW_RW1_SIGNALS = _as_bool(os.getenv("REGIME_ALLOW_RW1_SIGNALS"), False)
PAPER_TRADING_RELAX_RISK = _as_bool(os.getenv("PAPER_TRADING_RELAX_RISK"), True)

