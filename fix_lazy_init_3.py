import re

filepath = 'app/services/webhook_consumer.py'
with open(filepath, 'r') as f:
    content = f.read()

old_init = """    def __init__(self, broker: KrakenPaperBroker | None = None) -> None:
        self.broker = broker or KrakenPaperBroker()
        self.is_running = False
        self._task: asyncio.Task | None = None"""

new_init = """    def __init__(self, broker: KrakenPaperBroker | None = None) -> None:
        self.broker = broker
        self.is_running = False
        self._task: asyncio.Task | None = None"""

content = content.replace(old_init, new_init)

old_start = """    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("WebhookConsumer started")"""

new_start = """    def start(self) -> None:
        if self.is_running:
            return
        if self.broker is None:
            self.broker = KrakenPaperBroker()
        self.is_running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("WebhookConsumer started")"""

content = content.replace(old_start, new_start)

with open(filepath, 'w') as f:
    f.write(content)
