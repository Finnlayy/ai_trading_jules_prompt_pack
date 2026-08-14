from __future__ import annotations

import re
from pathlib import Path


FRONTEND = Path("frontend.html")


def _frontend_source() -> str:
    return FRONTEND.read_text(encoding="utf-8")


def test_all_button_tags_have_click_handler_or_submit_behavior():
    html = _frontend_source()
    missing_handlers: list[str] = []

    for match in re.finditer(r"<button\b[\s\S]*?>", html):
        tag = re.sub(r"\s+", " ", match.group(0)).strip()
        if "onClick=" in tag or 'type="submit"' in tag:
            continue
        line = html[: match.start()].count("\n") + 1
        snippet = re.sub(r"\s+", " ", html[match.start() : match.start() + 160]).strip()
        missing_handlers.append(f"line {line}: {snippet}")

    assert missing_handlers == []


def test_all_form_controls_have_state_or_disabled_wiring():
    html = _frontend_source()
    disconnected_controls: list[str] = []

    for tag_name in ("input", "select"):
        for match in re.finditer(rf"<{tag_name}\b[\s\S]*?>", html):
            tag = re.sub(r"\s+", " ", match.group(0)).strip()
            if "onChange=" in tag or "readOnly" in tag or "disabled=" in tag:
                continue
            line = html[: match.start()].count("\n") + 1
            disconnected_controls.append(f"line {line}: {tag}")

    assert disconnected_controls == []


def test_strategy_refresh_button_is_wired_to_real_loader():
    html = _frontend_source()

    assert "function fetchStrategyHealth()" in html
    assert 'onRefresh={() => {}}' not in html
    assert "onRefresh={fetchStrategyHealth}" in html


def test_backtest_strategy_selector_is_wired_to_backend_strategy_contract():
    html = _frontend_source()

    assert "strats.available_strategies || strats.strategies || []" in html
    assert "strategy_id: backtest.strategy_id || null" in html
    assert "availableStrategies={availableStrategies}" in html
    assert 'name="strategy_id"' in html
    assert 'name="min_confluence"' in html
    assert 'onChange={e => update("strategy_id", e.target.value)}' in html


def test_ppo_academy_backtesting_controls_are_wired_to_api_contract():
    html = _frontend_source()

    assert "PPO Academy Backtesting" in html
    assert 'data-testid="ppo-academy-backtesting-panel"' in html
    assert 'name="ppo_backend"' in html
    assert 'name="ppo_target_scout_index"' in html
    assert 'name="ppo_min_reward"' in html
    assert 'name="ppo_min_accuracy"' in html
    assert 'name="ppo_initial_cash"' in html
    assert 'name="ppo_records_json"' in html
    assert '"/academy/policy/backtesting/run"' in html
    assert '"/academy/policy/backtesting/optimize"' in html
    assert '"/academy/policy/backtesting/report"' in html
    assert "runPpoAction(\"run\")" in html
    assert "runPpoAction(\"optimize\")" in html
    assert "runPpoAction(\"report\")" in html


def test_ctrader_refresh_button_uses_component_callback_prop():
    html = _frontend_source()

    assert "function CTraderPanel({ state, setState, onPlaceOrder, onRefresh, loading })" in html
    assert "<button onClick={onRefresh} disabled={loading.ctrader}>Refresh</button>" in html
    assert "fetchCTraderStatus(); fetchCTraderBalance(); fetchCTraderSymbols();" in html


def test_ctrader_place_button_keeps_dry_run_clickable_without_live_readiness():
    html = _frontend_source()

    assert 'const canPlaceOrder = isLive ? isReady : status.mode === "dry-run";' in html
    assert "disabled={loading.ctrader || !canPlaceOrder}" in html
    assert "fetchCTraderStatus();" in html
    assert "fetchCTraderBalance();" in html
    assert "fetchCTraderSymbols();" in html


def test_layout_merge_preserves_new_panel_defaults_for_visible_nav_tabs():
    html = _frontend_source()

    assert "const DEFAULT_LAYOUT_CONFIG" in html
    assert "function mergeLayoutConfig(saved)" in html
    assert "ctrader: true" in html
    assert "...DEFAULT_LAYOUT_CONFIG.panels" in html
    assert "...(saved?.panels || {})" in html


def test_live_paper_buttons_share_real_loop_loading_state():
    html = _frontend_source()

    assert "const [loading, setLoading] = useState({ loop: false });" in html
    assert "function setLoopLoading(value)" in html
    assert "disabled={loading.loop || loopRunning}" in html


def test_deploy_agent_button_calls_backend_endpoint():
    html = _frontend_source()

    assert 'id="deploy-new-agent-btn"' in html
    assert "onClick={onDeployAgent}" in html
    assert '"/academy/agents/deploy"' in html


def test_learning_tab_surfaces_lifecycle_endpoints():
    html = _frontend_source()

    assert '"Learning"' in html
    assert "function LifecycleLearningPanel({ request, addLog })" in html
    assert 'request("/lifecycle/summary")' in html
    assert 'request("/lifecycle/engine/status")' in html
    assert 'request("/lifecycle/engine/control"' in html
    assert 'request("/lifecycle/outcomes?limit=25")' in html
    assert 'request("/lifecycle/learning?limit=50")' in html
    assert 'request("/academy/agents/careers/recent?limit=25&event_type=prediction_result")' in html
    assert 'request("/lifecycle/candidates?limit=25")' in html
    assert 'data-testid="lifecycle-learning-panel"' in html
    assert 'data-testid="paper-training-engine-controls"' in html
    assert 'data-testid="paper-outcomes-table"' in html
    assert 'data-testid="scout-learning-table"' in html
    assert 'data-testid="academy-career-outcomes-table"' in html


def test_ai_detail_surfaces_weighted_scout_vote():
    html = _frontend_source()

    assert "latestTrace.weighted_scout_vote" in html
    assert 'data-testid="weighted-scout-vote-panel"' in html
    assert "Confidence call dedupe" in html
