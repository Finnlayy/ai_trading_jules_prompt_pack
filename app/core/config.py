import os

# API configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", "kimi") # "kimi" or "gemini"

MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"
MOONSHOT_MODEL = "moonshot-v1-auto"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-pro"

# core config placeholder
MIN_RR_RATIO = 2.0
MAX_SPREAD = 15.0
MIN_CONFLUENCE_SCORE = 70.0
MAX_CRISIS_SCORE = 30.0
MAX_MC_DISPERSION = 5.0
MAX_DAILY_DRAWDOWN = 1000.0
MAX_TRADES_PER_DAY = 5
COOLDOWN_BARS = 3
