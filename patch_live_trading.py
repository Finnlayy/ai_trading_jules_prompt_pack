with open("app/api/live_trading.py", "r") as f:
    content = f.read()

trading_close_old = """@router.post("/positions/{trade_id}/close")
async def close_position(trade_id: str):
    \"\"\"Manually close an open position.\"\"\"
    p = live_fill_tracker.get_position(trade_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Position not found")
    live_fill_tracker.record_exit(trade_id, p.current_price)
    return {"success": True, "trade_id": trade_id, "closed_at": datetime.now(timezone.utc).isoformat()}"""

trading_close_new = """@router.post("/positions/{trade_id}/close")
async def close_position(trade_id: str):
    \"\"\"Manually close an open position.\"\"\"
    p = live_fill_tracker.get_position(trade_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Position not found")
    live_fill_tracker.record_exit(trade_id, p.current_price)
    live_fill_tracker.flush_db_exit_queue()
    return {"success": True, "trade_id": trade_id, "closed_at": datetime.now(timezone.utc).isoformat()}"""

content = content.replace(trading_close_old, trading_close_new)

trading_stop_old = """    if req.close_open_positions:
        for p in live_fill_tracker.get_open_positions():
            live_fill_tracker.record_exit(p.trade_id, p.current_price)
            positions_closed += 1

    autonomous_loop_instance.pause()"""

trading_stop_new = """    if req.close_open_positions:
        for p in live_fill_tracker.get_open_positions():
            live_fill_tracker.record_exit(p.trade_id, p.current_price)
            positions_closed += 1
        if positions_closed > 0:
            live_fill_tracker.flush_db_exit_queue()

    autonomous_loop_instance.pause()"""

content = content.replace(trading_stop_old, trading_stop_new)

with open("app/api/live_trading.py", "w") as f:
    f.write(content)
