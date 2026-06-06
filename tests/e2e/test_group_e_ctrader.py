"""Group E RED tests: cTrader Panel visibility and order form."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def test_ctrader_panel_renders_connection_status(page: Page):
    """cTrader tab must show connection status pill."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)

    # Click cTrader tab
    page.locator('nav button[data-label="cTrader"]').click()

    # Wait for panel to render
    page.wait_for_selector('text=cTrader', timeout=10_000)

    # Connection status pill should be visible
    pill = page.locator('.panel-title .pill').filter(has_text=re.compile(r'Connected|Disconnected'))
    expect(pill).to_be_visible()


def test_ctrader_panel_has_symbol_selector(page: Page):
    """cTrader panel must include a symbol dropdown."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)

    page.locator('nav button[data-label="cTrader"]').click()
    page.wait_for_selector('text=Place Market Order', timeout=10_000)

    # Symbol select should exist
    select = page.locator('select').filter(has_text=re.compile(r'EURUSD|BTCUSDT'))
    expect(select).to_be_visible()


def test_ctrader_panel_has_order_form(page: Page):
    """cTrader panel must have direction toggle, lots input, and place order button."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)

    page.locator('nav button[data-label="cTrader"]').click()
    page.wait_for_selector('text=Place Market Order', timeout=10_000)

    # Direction buttons
    expect(page.locator('button:has-text("Buy")')).to_be_visible()
    expect(page.locator('button:has-text("Sell")')).to_be_visible()

    # Lots input (number type)
    lots_input = page.locator('section:not(.hidden) input[type="number"]').first
    expect(lots_input).to_be_visible()

    # Place order button
    expect(page.locator('button:has-text("Place Dry-Run Order")')).to_be_visible()


def test_ctrader_order_submit_shows_result(page: Page):
    """Clicking Place Order should show a result card."""
    page.goto("http://localhost:8000/", timeout=60_000)
    page.wait_for_selector("nav", timeout=10_000)

    page.locator('nav button[data-label="cTrader"]').click()
    page.wait_for_selector('text=Place Market Order', timeout=10_000)

    # Click place order
    page.locator('button:has-text("Place Dry-Run Order")').click()

    # Wait for result to appear
    page.wait_for_selector('text=Last Order Result', timeout=10_000)
    result_status = page.locator('.panel span.pill').filter(has_text=re.compile(r'DRY_RUN|SENT_TO_CTRADER|ERROR'))
    expect(result_status).to_be_visible()
