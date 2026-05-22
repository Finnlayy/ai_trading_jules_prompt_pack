import os


# Keep tests deterministic regardless of local .env content.
os.environ["AI_PROVIDER"] = "moonshot"
os.environ["BROKER_MODE"] = "simulation"
os.environ["PIONEX_RELAY_ENABLED"] = "false"
os.environ["PIONEX_DIRECT_ENABLED"] = "false"
os.environ["PIONEX_DIRECT_LIVE_TRADING_ENABLED"] = "false"
os.environ["AI_FAILURE_POLICY"] = "reject_live"
