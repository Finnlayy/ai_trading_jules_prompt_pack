# Trading Engine & Pionex Live-Execution Fix

The user requested to fix the live-execution logic ("Kopiereinschalten") so that the bot visually confirms Pionex trades. Additionally, they requested a separate widget ("Trading Engine Widget") that allows controlling the live feeds via sliders and displaying the history of executed trades.

## Analysis & Current Bugs
1. **Trade Execution State Bug**: In `YoutubeAnalyzer.tsx`, the simulated execution calls `exchangeService.executeTrade`. However, when the execution succeeds asynchronously, the code mutates `newSignal.tradeExecuted = true` directly without calling `setGlobalHistory`, thus the React UI never re-renders to show the executed trade.
2. **Exchange Service Credential Error**: The `exchangeService` throws an Error if Pionex API keys are missing. For demo/preview mode, it should simulate the trade execution successfully with a "Demo Gateway" warning so the user can verify the UI workflow before inserting real API keys.
3. **Missing Component**: We need a dedicated widget to act as a centralized "Trading Engine" which fulfills the user's explicit request.

## Proposed Changes

### 1. Update `src/services/exchangeService.ts`
Modify `executeTrade` to handle empty API keys by gracefully falling back to a "Demo Mode" instead of throwing a hard error. This allows the visual components to verify execution logic without demanding valid keys upfront.

#### [MODIFY] `exchangeService.ts`
- Remove the `throw new Error()` for missing Pionex credentials.
- Add a console warning indicating that the transaction is being executed in Demo Mode.

### 2. Update `src/components/YoutubeAnalyzer.tsx`
Fix the React state update when a trade is executed, and integrate the new widget.

#### [MODIFY] `YoutubeAnalyzer.tsx`
- Inside the simulation loop, gracefully handle the async resolution of `executeTrade`. When resolved successfully, call `setGlobalHistory` and `setPinnedStreams` to update the specific signal's `tradeExecuted` property so it triggers a re-render.
- Add an import for `<TradingEngineWidget />` and place it intelligently (e.g. in the left column above the main signal log).

### 3. Create `src/components/news/TradingEngineWidget.tsx`
Build the new Trading Engine widget.

#### [NEW] `TradingEngineWidget.tsx`
- **Props**: `pinnedStreams`, `onToggleCopying`, `globalHistory`
- **Structure**:
  - **Live Feeds Control**: A list of currently active streams. Each stream will have a `Switch` (Slider) tied to `onToggleCopying` to independently arm or disarm the copy-trading bot for that stream.
  - **Executed Trades Log**: A `ScrollArea` that filters `globalHistory` for items where `tradeExecuted === true`. It will display the execution time, amount, matched symbol, and profit estimation.

## User Review Required
> [!IMPORTANT]
> - Is placing the new "Trading Engine Widget" in the left column beneath the stream input fields acceptable, or would you prefer it in a separate tab?
> - Let me know if you are satisfied with this plan so we can proceed with execution!
