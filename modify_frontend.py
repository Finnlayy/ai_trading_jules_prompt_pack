import re

with open("frontend.html", "r") as f:
    content = f.read()

orig_ui = """                                <div className="backtest-chart-container" style={{ height: 320, border: "1px solid var(--line)", borderRadius: "var(--radius-sm)", marginBottom: 16, position: "relative" }}>
                                    {backtestResult.results && backtestResult.results.map((r, i) => (
                                        <div key={i} style={{ position: "absolute", left: `${(i / Math.max(backtestResult.results.length, 1)) * 90 + 5}%`, top: "10%" }}>
                                            <div data-marker-type="entry" style={{ width: 8, height: 8, background: "#33a56b", borderRadius: "50%" }} />
                                            <div data-marker-type="exit" style={{ width: 8, height: 8, background: "#d86545", borderRadius: "50%", marginTop: 4 }} />
                                        </div>
                                    ))}
                                </div>"""

new_ui = """                                <div className="backtest-chart-container" style={{ minHeight: 320, border: "1px solid var(--line)", borderRadius: "var(--radius-sm)", marginBottom: 16, overflow: "hidden", background: "#0a0a0a" }}>
                                    {backtestResult.chart_base64 ? (
                                        <img
                                            src={`data:image/png;base64,${backtestResult.chart_base64}`}
                                            alt="Backtest Equity & Drawdown Chart"
                                            style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
                                        />
                                    ) : (
                                        <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>No chart trace data generated.</div>
                                    )}
                                </div>"""

content = content.replace(orig_ui, new_ui)

with open("frontend.html", "w") as f:
    f.write(content)

print("Modification complete.")
