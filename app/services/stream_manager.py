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

    async def connect(self):
        self.running = True
        while self.running:
            try:
                async with websockets.connect(self.uri) as websocket:
                    self.connection = websocket
                    logger.info(f"Connected to stream: {self.uri}")
                    await self._listen(websocket)
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                if self.running:
                    await asyncio.sleep(5) # Reconnect backoff

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
