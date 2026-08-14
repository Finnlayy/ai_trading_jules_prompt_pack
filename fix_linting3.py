import re

# Fix app/main.py globals
filepath = 'app/main.py'
with open(filepath, 'r') as f:
    content = f.read()

# In startup_event
content = content.replace(
    "    global _heartbeat_task, _news_poll_task, _autostart_task, _training_autostart_task, _price_poller_task, _shadow_queue_task",
    "    global _heartbeat_task, _news_poll_task, _autostart_task, _training_autostart_task, _shadow_queue_task"
)

# In shutdown_event
# Just remove the global declaration entirely since it's only reading
content = content.replace(
    "\n    global _heartbeat_task, _news_poll_task, _autostart_task, _training_autostart_task, _shadow_queue_task",
    ""
)

with open(filepath, 'w') as f:
    f.write(content)

# Fix app/services/perception_engine.py
filepath = 'app/services/perception_engine.py'
with open(filepath, 'r') as f:
    content = f.read()

# It uses `market_data_service.get_latest_bar(symbol)` but market_data_service isn't imported.
# But wait, looking at `perception_engine.py` it has:
# `from app.services.market_data_service import market_data_service` ? No, I checked and that file doesn't exist.
