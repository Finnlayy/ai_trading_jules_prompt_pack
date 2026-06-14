import asyncio
import json
import logging
import websockets

logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self, uri="wss://stream.binance.com:9443/ws/btcusdt@trade"):
        self.uri = uri
        self.connection = None
        self.running = False
        self.min_delay = 1
        self.max_delay = 60

    async def connect(self):
        self.running = True
        delay = self.min_delay
        while self.running:
            try:
                async with websockets.connect(self.uri) as websocket:
                    self.connection = websocket
                    logger.info(f"Connected to stream: {self.uri}")
                    delay = self.min_delay # reset delay on successful connection
                    await self._listen(websocket)
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                if self.running:
                    import random
                    # Exponential backoff with jitter
                    sleep_time = delay + random.uniform(0, 1)
                    await asyncio.sleep(sleep_time)
                    delay = min(delay * 2, self.max_delay)

    async def _listen(self, websocket):
        try:
            async for message in websocket:
                data = json.loads(message)
                # Process tick data
                logger.debug(f"Received tick: {data}")
        except websockets.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error parsing message: {e}")

    async def stop(self):
        self.running = False
        if self.connection:
            await self.connection.close()

stream_manager = StreamManager()
