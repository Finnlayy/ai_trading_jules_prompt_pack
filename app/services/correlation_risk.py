"""
Correlation Risk Checker — prevents over-concentration in correlated assets.

Sector mapping (simplified):
  CRYPTO   : BTC, ETH, SOL, HYPE, etc.
  FOREX    : EUR, GBP, JPY, etc.
  METALS   : XAG, XAU
  INDICES  : SPX, NDX
  COMMODITIES : OIL, GAS

Gate: if portfolio already has >= MAX_SECTOR_POSITIONS in the same sector,
reject new entry in that sector.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Simplified sector mapping based on symbol prefixes.
# Order matters: longer/more specific prefixes should come first.
SECTOR_MAP: Dict[str, str] = {
    "XAG": "METALS",
    "XAU": "METALS",
    "BTC": "CRYPTO",
    "ETH": "CRYPTO",
    "SOL": "CRYPTO",
    "HYPE": "CRYPTO",
    "DOGE": "CRYPTO",
    "XRP": "CRYPTO",
    "EUR": "FOREX",
    "GBP": "FOREX",
    "JPY": "FOREX",
    "USD": "FOREX",
    "SPX": "INDICES",
    "NDX": "INDICES",
    "OIL": "COMMODITIES",
    "GAS": "COMMODITIES",
}

# Default max positions per sector
MAX_SECTOR_POSITIONS = 2


class CorrelationRiskChecker:
    def __init__(self, max_per_sector: int = MAX_SECTOR_POSITIONS) -> None:
        self.max_per_sector = max_per_sector

    def _sector(self, symbol: str) -> str:
        symbol_upper = symbol.upper()
        for prefix, sector in SECTOR_MAP.items():
            if prefix in symbol_upper:
                return sector
        return "OTHER"

    def check_new_entry(
        self,
        symbol: str,
        open_positions: List[dict],
    ) -> dict:
        """
        Check if adding a new position in `symbol` would violate correlation limits.
        open_positions: list of dicts with at least {'symbol': str}
        Returns {allowed, reason, sector, current_count}
        """
        sector = self._sector(symbol)
        if sector == "OTHER":
            return {"allowed": True, "reason": "", "sector": sector, "current_count": 0}

        current_count = sum(
            1 for pos in open_positions if self._sector(pos.get("symbol", "")) == sector
        )

        if current_count >= self.max_per_sector:
            return {
                "allowed": False,
                "reason": f"Sector {sector} already has {current_count} positions (max {self.max_per_sector})",
                "sector": sector,
                "current_count": current_count,
            }

        return {
            "allowed": True,
            "reason": "",
            "sector": sector,
            "current_count": current_count,
        }


# Global instance
correlation_checker = CorrelationRiskChecker()
