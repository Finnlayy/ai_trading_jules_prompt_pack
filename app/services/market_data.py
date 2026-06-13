class MarketDataService:
    async def fetch_latest(self, symbol):
        return {"price": 100}
    async def get_recent_candles(self, symbol, timeframe, limit=100):
        return []
market_data_service = MarketDataService()
