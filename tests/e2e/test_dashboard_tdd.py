import pytest
from playwright.sync_api import Page, expect

@pytest.fixture(scope="session")
def live_server_url():
    return "http://127.0.0.1:8000"

def test_zen_mode_default(page: Page, live_server_url):
    page.goto(live_server_url)

    # 1. Assert Zen Mode is default
    # The mode toggle button should exist and indicate Zen Mode is active
    toggle_btn = page.locator("button[data-testid='mode-toggle']")
    expect(toggle_btn).to_be_visible()
    expect(page.locator("body")).to_have_attribute("data-layout-mode", "zen")

def test_terminal_mode_switch(page: Page, live_server_url):
    page.goto(live_server_url)

    # 2. Assert switching to Terminal Mode
    toggle_btn = page.locator("button[data-testid='mode-toggle']")
    toggle_btn.click()

    expect(page.locator("body")).to_have_attribute("data-layout-mode", "terminal")

    # Check for core widgets in terminal mode
    expect(page.locator("div[data-testid='watchlist-widget']")).to_be_visible()
    expect(page.locator("div[data-testid='chart-widget']")).to_be_visible()
    expect(page.locator("div[data-testid='order-ticket-widget']")).to_be_visible()

def test_dynamic_linking(page: Page, live_server_url):
    page.goto(live_server_url)

    # Switch to terminal mode first
    page.locator("button[data-testid='mode-toggle']").click()

    # Click on a watchlist item (e.g. BTC_USDT)
    watchlist_item = page.locator("div[data-testid='watchlist-item-BTC_USDT']")
    watchlist_item.click()

    # Check if chart and order ticket are updated
    chart_title = page.locator("div[data-testid='chart-title']")
    expect(chart_title).to_contain_text("BTC_USDT")

    order_symbol_input = page.locator("input[data-testid='order-symbol-input']")
    expect(order_symbol_input).to_have_value("BTC_USDT")

def test_color_heuristic_red_green(page: Page, live_server_url):
    page.goto(live_server_url)

    # In Zen mode, we should have a portfolio value or some metrics
    # We can test rendering of positive and negative values by injecting state or mock
    # For now, let's just assume we have some test elements on the page
    # This might need to be refined once we start building the components
    positive_element = page.locator("div[data-testid='metric-positive']")
    negative_element = page.locator("div[data-testid='metric-negative']")

    # The class should be related to the colors we specified
    # We will implement this with Tailwind or custom CSS classes
    if positive_element.is_visible():
        expect(positive_element).to_have_class(re.compile(r"text-mint-strong|text-green"))
    if negative_element.is_visible():
        expect(negative_element).to_have_class(re.compile(r"text-peach-strong|text-red"))

def test_order_ticket_submission(page: Page, live_server_url):
    page.goto(live_server_url)
    page.locator("button[data-testid='mode-toggle']").click()

    # Setup order ticket
    page.locator("div[data-testid='watchlist-item-ETH_USDT']").click()

    buy_btn = page.locator("button[data-testid='order-buy-btn']")
    buy_btn.click()

    # Wait for success toast
    toast = page.locator("div[data-testid='success-toast']")
    expect(toast).to_be_visible()
    expect(toast).to_contain_text("Order placed")
