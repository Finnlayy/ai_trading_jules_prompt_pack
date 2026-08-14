import re

# 1. Fix app/api/orchestrator.py
filepath = 'app/api/orchestrator.py'
with open(filepath, 'r') as f:
    content = f.read()

# Check if import is already there
if "from app.services.confidence_registry import confidence_registry" not in content:
    # Add import at the top
    content = content.replace("from app.services.journal_logger import journal_logger_instance", "from app.services.journal_logger import journal_logger_instance\nfrom app.services.confidence_registry import confidence_registry")
    with open(filepath, 'w') as f:
        f.write(content)

# 2. Fix app/main.py
filepath = 'app/main.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace global _price_poller_task etc.
content = content.replace("global _heartbeat_task, _news_poll_task, _autostart_task, _training_autostart_task, _price_poller_task, _shadow_queue_task", "global _heartbeat_task, _news_poll_task, _autostart_task, _training_autostart_task, _shadow_queue_task")
# _price_poller_task is unused in startup, it's just price_poller.start(). Let's remove variables that are never assigned: _price_poller_task.
# Wait, let's look closer at app/main.py globals
