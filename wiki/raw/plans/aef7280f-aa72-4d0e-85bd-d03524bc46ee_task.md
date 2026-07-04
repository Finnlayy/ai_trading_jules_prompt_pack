# Task List: Trading Engine & Live Execution

- `[x]` Update `src/services/exchangeService.ts` to simulate trades gracefully without throwing if API keys are missing.
- `[x]` Update `PinnedStream` interface in `src/components/news/PinnedStreamWidget.tsx` to include `tradeSymbol` and `tradeAmount`.
- `[x]` Create `src/components/news/TradingEngineWidget.tsx` with list of streams, Symbol/Amount inputs, on/off sliders, and executed trades log.
- `[x]` Update `src/components/YoutubeAnalyzer.tsx` to handle state for `tradeExecuted` properly, use `tradeAmount` & `tradeSymbol` when calling `executeTrade`, and integrate the new `TradingEngineWidget`.
