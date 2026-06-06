"""Group C RED tests: Agent Deployment & Metrics (Bugs 6, 7)."""

from __future__ import annotations

from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Bug 6 — Missing Agent Metrics (UI)
# ---------------------------------------------------------------------------
def test_agent_profile_card_renders_metrics(page: Page):
    """RED: Agent profile card must visibly render confidence_level and experience_level."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)
    page.locator('nav button[data-label="Agents"]').click()

    card = page.locator(".agent-profile-card").first
    expect(card).to_be_visible(timeout=5_000)
    text = card.inner_text()
    assert "confidence_level" in text or "Confidence" in text or "CONFIDENCE" in text, (
        "Agent card missing confidence_level display"
    )
    assert "experience_level" in text or "Experience" in text or "EXPERIENCE" in text, (
        "Agent card missing experience_level display"
    )


# ---------------------------------------------------------------------------
# Bug 7 — Deployment UI & Status List
# ---------------------------------------------------------------------------
def test_deploy_new_agent_button_exists(page: Page):
    """RED: UI must contain a functional #deploy-new-agent-btn."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)
    page.locator('nav button[data-label="Agents"]').click()

    btn = page.locator("#deploy-new-agent-btn")
    expect(btn).to_be_visible(timeout=5_000)
    expect(btn).to_be_enabled(timeout=3_000)


def test_agent_quick_list_with_statuses(page: Page):
    """RED: Quick List must show agent names and mapped statuses."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)
    page.locator('nav button[data-label="Agents"]').click()

    quick_list = page.locator(".agent-quick-list")
    expect(quick_list).to_be_visible(timeout=5_000)
    text = quick_list.inner_text()

    required_statuses = ["Waiting for setup", "In trade", "In training"]
    text_lower = text.lower()
    found = [s for s in required_statuses if s.lower() in text_lower]
    assert len(found) > 0, (
        f"Agent quick list missing required statuses. Found: {text}"
    )
