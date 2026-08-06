import re
with open('app/services/pionex_direct_broker.py', 'r') as f:
    content = f.read()

helpers = """
    def _validate_open_position(self, payload, symbol: str, account_mode: str, ai_decision, war_room) -> "TradeJournalEntry | None":
        if war_room.reject_reason:
            self.notifier.send_reject(symbol, war_room.reject_reason, f"pionex-direct-{payload.signal_id}", payload.intent)
            return self._build_entry(
                payload=payload,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                reject_reason=war_room.reject_reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={
                    "status": "REJECTED",
                    "reject_reason": war_room.reject_reason,
                    "war_room": war_room.to_dict(),
                },
            )

        if account_mode == "SPOT" and payload.direction == "SHORT":
            reason = "SPOT_SHORT_NOT_SUPPORTED"
            self.notifier.send_reject(symbol, reason, f"pionex-direct-{payload.signal_id}", payload.intent)
            return self._build_entry(
                payload=payload,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                reject_reason=reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reason},
            )
        return None

    def _get_balance_for_sizing(self, account_mode: str) -> float:
        if self.client is None:
            balance = 0.0
        else:
            try:
                balance = self.client.get_balance(coin="USDT", account="spot" if account_mode == "SPOT" else "futures")
            except PionexAPIError:
                balance = 0.0

        if balance <= 0:
            # Keep deterministic minimum sizing in dry/limited environments.
            balance = 100.0
        return balance

    def _open_position(self, payload: M8Payload, symbol: str, account_mode: str, ai_decision: AIDecisionEnum) -> TradeJournalEntry:
        war_room = classify_order(payload)

        rejection_entry = self._validate_open_position(payload, symbol, account_mode, ai_decision, war_room)
        if rejection_entry:
            return rejection_entry

        balance = self._get_balance_for_sizing(account_mode)

        sizing = self.sizer.size_trade(
            payload,
            balance=balance,
            risk_cap_pct=war_room.risk_cap_pct,
        )"""

# Find _open_position definition
pattern = re.compile(r'    def _open_position\(.*?\).*?        sizing = self\.sizer\.size_trade\(\n            payload,\n            balance=balance,\n            risk_cap_pct=war_room\.risk_cap_pct,\n        \)', re.DOTALL)

if pattern.search(content):
    new_content = pattern.sub(helpers.lstrip('\n'), content, count=1)
    with open('app/services/pionex_direct_broker.py', 'w') as f:
        f.write(new_content)
    print("Patched successfully")
else:
    print("Could not find pattern to patch")
