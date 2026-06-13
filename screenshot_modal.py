from playwright.sync_api import sync_playwright
import time
import base64

def test_screenshot():
    # Mock base64 chart
    with open("test_chart.png", "wb") as f:
        # Generate dummy 1x1 png base64
        pass # Not strictly needed if we just inject the html

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            :root {
                --surface: #1e1e1e;
                --line: #333;
                --radius: 8px;
                --radius-sm: 4px;
                --muted: #888;
            }
            body { background: #121212; color: white; font-family: sans-serif; }
        </style>
    </head>
    <body>
        <div id="backtest-result-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 2000; display: flex; align-items: center; justify-content: center;">
            <div style="background: var(--surface); border-radius: var(--radius); padding: 24px; width: 90vw; max-width: 900px; max-height: 90vh; overflow: auto; border: 1px solid var(--line);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="margin: 0;">Backtest Results: HYPEUSDT</h3>
                    <button>Close</button>
                </div>
                <div class="backtest-chart-container" style="min-height: 320px; border: 1px solid var(--line); border-radius: var(--radius-sm); margin-bottom: 16px; overflow: hidden; background: #0a0a0a;">
                    <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" alt="Backtest Equity & Drawdown Chart" style="width: 100%; height: 100%; object-fit: contain; display: block;" />
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;">
                    <div><div class="kpi-caption">Signals</div><div class="kpi-value">50</div></div>
                    <div><div class="kpi-caption">Executed</div><div class="kpi-value">25</div></div>
                    <div><div class="kpi-caption">Rejected</div><div class="kpi-value">25</div></div>
                    <div><div class="kpi-caption">Longs/Shorts</div><div class="kpi-value">10/15</div></div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    with open("test_modal.html", "w") as f:
        f.write(html_content)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("file:///app/test_modal.html")
        time.sleep(1)
        page.screenshot(path="modal_screenshot.png")
        browser.close()

if __name__ == "__main__":
    test_screenshot()
