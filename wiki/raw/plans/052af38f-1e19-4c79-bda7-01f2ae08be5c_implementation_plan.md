# Implementation Plan - Direct Tool/Action Routing to Chat

Currently, the `/ai/chat` endpoint only parses and processes the `reply` and `profile_patch` from the AI response. We will extend the backend router in `app/api/ai_layer.py` to parse, validate, and execute `recommended_action` on behalf of the user.

## User Review Required

> [!IMPORTANT]
> - All executed actions are restricted to a predefined list of safe actions (backtesting, synthetic drills, training, resetting memory, emergency stop).
> - Live trading cannot be enabled or bypassed via this mechanism.
> - The actions will execute synchronously (where possible) or trigger background tasks (for training loop state) and append their results to the chat response reply so the user is informed of the outcome.

## Proposed Changes

We will modify:
1. [ai_layer.py](file:///g:/Downloads_Sortiert_2026-05-20/ai_trading_jules_prompt_pack/app/api/ai_layer.py):
   - Modify the `chat_with_ai_layer` endpoint to:
     - Parse the `recommended_action` block from the LLM JSON response or from the local parser.
     - Call a helper router `execute_recommended_action` which executes the command and returns a feedback string.
     - Append the feedback string (if any) to the assistant's `reply`.
     - Include the executed `recommended_action` in the final `AIChatResponse`.
   - Update `_local_profile_patch` to support basic text trigger commands (e.g. if the user types "run backtest for BTCUSDT" or "start training") so that the fallback local parser can also suggest and execute a `recommended_action`.

### Allowed Actions and Mapping

1. **`run_backtest`**
   - Params: `symbol` (str), `days` (int, default 7), `bars` (int, default 500), `max_signals` (int, default 50), `min_confluence` (float, optional).
   - Execution: Import and call `run_backtest` from `app.api.backtest_runner` using a `BacktestRunRequest` payload.
   - Return feedback: Short summary of signals generated/executed/rejected (e.g. `[Action Executed: run_backtest] Generated 12 signals, executed 8, rejected 4.`).

2. **`trigger_drill`**
   - Params: `scout_name` (str, optional)
   - Execution: Import `training_loop` from `app.services.training_loop` and call `await training_loop.trigger_manual_cycle()`. (If a specific scout name is requested, we will run the drill cycle).
   - Return feedback: `[Action Executed: trigger_drill] Drill cycle triggered successfully.`

3. **`start_training`**
   - Params: none
   - Execution: Import `training_loop` and call `await training_loop.start()`.
   - Return feedback: `[Action Executed: start_training] Academy training loop started.`

4. **`stop_training`**
   - Params: none
   - Execution: Import `training_loop` and call `await training_loop.stop()`.
   - Return feedback: `[Action Executed: stop_training] Academy training loop stopped.`

5. **`reset_memory`**
   - Params: none
   - Execution: Import `ai_layer_memory_instance` and call `ai_layer_memory_instance.reset()`.
   - Return feedback: `[Action Executed: reset_memory] AI layer memory and profile reset.`

6. **`toggle_emergency`**
   - Params: `active` (bool)
   - Execution:
     - If `active` is `True`: Set `app.api.live_trading._emergency_halt_until` to `now + 24 hours` and call `autonomous_loop_instance.pause()`.
     - If `active` is `False`: Set `app.api.live_trading._emergency_halt_until` to `None`.
   - Return feedback: `[Action Executed: toggle_emergency] Emergency halt activated.` or `[Action Executed: toggle_emergency] Emergency halt deactivated.`

## Verification Plan

### Automated Tests
- Run `pytest tests/api/test_ai_layer.py` (if it exists) or write a new test `tests/api/test_ai_layer_routing.py` to verify that sending requests triggers correct actions and returns the routing feedback.

### Manual Verification
- Start FastAPI server using `uvicorn app.main:app --reload --port 8000`.
- Send custom POST requests to `/ai/chat` to test each action and verify it performs the expected behavior and modifies the system state accordingly.
