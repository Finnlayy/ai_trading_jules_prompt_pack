with open("app/services/position_monitor.py", "r") as f:
    content = f.read()

monitor_old = """        for ex in exits:
            live_fill_tracker.record_exit(ex.trade_id, ex.exit_price)
            closed.append({
                "trade_id": ex.trade_id,
                "symbol": ex.symbol,
                "direction": ex.direction,
                "exit_price": ex.exit_price,
                "exit_reason": ex.exit_reason,
                "pnl_estimate": ex.pnl_estimate,
            })
            dashboard_sse_manager.broadcast_alert(
                f"Position {ex.trade_id} closed: {ex.exit_reason} @ {ex.exit_price}",
                level="info" if ex.exit_reason == "TAKE_PROFIT" else "warning",
            )"""

monitor_new = """        for ex in exits:
            live_fill_tracker.record_exit(ex.trade_id, ex.exit_price)
            closed.append({
                "trade_id": ex.trade_id,
                "symbol": ex.symbol,
                "direction": ex.direction,
                "exit_price": ex.exit_price,
                "exit_reason": ex.exit_reason,
                "pnl_estimate": ex.pnl_estimate,
            })
            dashboard_sse_manager.broadcast_alert(
                f"Position {ex.trade_id} closed: {ex.exit_reason} @ {ex.exit_price}",
                level="info" if ex.exit_reason == "TAKE_PROFIT" else "warning",
            )

        # Ensure queued DB exits are flushed
        if exits:
            live_fill_tracker.flush_db_exit_queue()"""

content = content.replace(monitor_old, monitor_new)

with open("app/services/position_monitor.py", "w") as f:
    f.write(content)
