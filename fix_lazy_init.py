import re

filepath = 'app/services/position_monitor.py'
with open(filepath, 'r') as f:
    content = f.read()

old_init = """    def __init__(self, broker: KrakenPaperBroker | None = None) -> None:
        self.broker = broker or KrakenPaperBroker()
        self.is_running = False
        self._task: asyncio.Task | None = None
        self.check_interval_seconds = 5.0"""

new_init = """    def __init__(self, broker: KrakenPaperBroker | None = None) -> None:
        self.broker = broker
        self.is_running = False
        self._task: asyncio.Task | None = None
        self.check_interval_seconds = 5.0"""

content = content.replace(old_init, new_init)

old_start = """    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._monitor_loop())"""

new_start = """    def start(self) -> None:
        if self.is_running:
            return
        if self.broker is None:
            self.broker = KrakenPaperBroker()
        self.is_running = True
        self._task = asyncio.create_task(self._monitor_loop())"""

content = content.replace(old_start, new_start)

with open(filepath, 'w') as f:
    f.write(content)
