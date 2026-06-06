"""Group A RED tests: Stability & Visibility (Bugs 1, 2, 3)."""

from __future__ import annotations

from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Bug 3 — Z-Index Tooltip Hiding (Playwright DOM assertion)
# ---------------------------------------------------------------------------
def test_sidebar_tooltip_z_index_above_panels(page: Page):
    """RED: Sidebar icon tooltip must have higher z-index than adjacent panels."""
    page.goto("http://localhost:8000/", timeout=60_000)
    # Wait for nav to render
    page.wait_for_selector("nav", timeout=10_000)

    # Hover first nav button with data-label
    button = page.locator('nav button[data-label="Overview"]')
    button.hover()

    # Grab the tooltip pseudo-element via JS (browsers expose ::after on element)
    tooltip_z = button.evaluate("""
        (el) => {
            const style = window.getComputedStyle(el, '::after');
            return parseInt(style.zIndex, 10);
        }
    """)

    # Grab adjacent panel z-index
    panel_z = page.evaluate("""
        () => {
            const panel = document.querySelector('.panel');
            if (!panel) return 0;
            return parseInt(window.getComputedStyle(panel).zIndex, 10) || 0;
        }
    """)

    assert tooltip_z > panel_z, (
        f"Tooltip z-index ({tooltip_z}) must be strictly greater than panel z-index ({panel_z})"
    )
