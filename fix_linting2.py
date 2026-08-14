import re

# Fix app/main.py globals
filepath = 'app/main.py'
with open(filepath, 'r') as f:
    content = f.read()

content = content.replace("global _heartbeat_task, _news_poll_task, _autostart_task, _training_autostart_task, _price_poller_task, _shadow_queue_task", "global _heartbeat_task, _news_poll_task, _autostart_task, _training_autostart_task, _shadow_queue_task")
# The error was about `_price_poller_task` in startup. In shutdown, it was about `_heartbeat_task`, `_news_poll_task`, `_autostart_task`, `_training_autostart_task`, `_price_poller_task`, `_shadow_queue_task`.
# Why? Because in shutdown_event, they are declared global but NEVER reassigned. In python, you only need `global var` if you ASSIGN to it (like `var = ...`). If you only read or call methods on it, it's not strictly necessary, but `flake8` complains if you declare `global` and never assign to it in the function scope.
# Wait, let's just remove the `global ...` line from `shutdown_event` entirely, as it only reads `_heartbeat_task` and calls `.cancel()` on it (it doesn't assign to it, well wait, does it assign?).
