"""Group B RED tests: Agent Review & History UI (Bugs 4, 5)."""

from __future__ import annotations

from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Bug 4 — Agent Selection & Review Trace
# ---------------------------------------------------------------------------
def test_agent_dropdown_and_review_trace(page: Page):
    """RED: UI must render agent dropdown and filter review trace by selected agent."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)
    # Navigate to AI Layer or Control panel where agent selection should exist
    page.locator('nav button[data-label="AI Layer"]').click()

    # Assert agent select dropdown exists
    select = page.locator("select#agent-select")
    expect(select).to_be_visible(timeout=5_000)

    # Mock 3 options via direct JS injection (since backend may not serve them yet)
    page.evaluate("""
        () => {
            const sel = document.getElementById('agent-select');
            if (!sel) return;
            sel.innerHTML = `
                <option value="">Select agent</option>
                <option value="agent-live-1">Agent Alpha (live)</option>
                <option value="agent-live-2">Agent Beta (live)</option>
                <option value="agent-paper-1">Agent Gamma (paper)</option>
            `;
        }
    """)
    options = select.locator("option").all_inner_texts()
    assert len(options) == 4, f"Expected 4 options (incl placeholder), got {len(options)}"

    # Select paper agent
    select.select_option("agent-paper-1")

    # Assert review detail container updates
    detail = page.locator("#ai-review-detail")
    expect(detail).to_be_visible(timeout=3_000)
    detail_text = detail.inner_text()
    assert "Agent Gamma" in detail_text or "agent-paper-1" in detail_text, (
        f"Review detail did not filter to selected agent. Content: {detail_text}"
    )


# ---------------------------------------------------------------------------
# Bug 5 — Live/Sim Toggle & Detailed Trade List (UI)
# ---------------------------------------------------------------------------
def test_live_sim_toggle_and_winrate(page: Page):
    """RED: UI must expose live/sim toggle and winrate percentage."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)
    page.locator('nav button[data-label="Orders"]').click()

    toggle = page.locator(".live-sim-toggle")
    expect(toggle).to_be_visible(timeout=5_000)

    # Click to simulated view
    toggle.click()

    winrate = page.locator(".winrate-percentage")
    expect(winrate).to_be_visible(timeout=3_000)
