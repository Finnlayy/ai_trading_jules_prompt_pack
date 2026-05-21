#!/usr/bin/env python3
"""
Generate Pine Script v6 from GA optimization results.
Patches template with optimized genes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict


def load_ga_results(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def patch_template(template: str, genes: Dict, symbol: str = "HYPEUSDT") -> str:
    """Patch Pine Script template with GA-optimized parameters."""
    result = template

    # Update title and metadata
    result = re.sub(
        r'strategy\(\s*\n?\s*title\s*=\s*"[^"]*"',
        f'strategy(\n    title             = "{symbol}_GA_Optimized_v6"',
        result,
        count=1,
    )
    result = re.sub(
        r'shorttitle\s*=\s*"[^"]*"',
        f'shorttitle        = "{symbol}_GA"',
        result,
        count=1,
    )

    # Patch SL ATR multiplier
    if "sl_atr_mul" in genes:
        result = re.sub(
            r'(float sl_atr_mult = input\.float\(\s*\n?\s*defval\s*=\s*)[\d.]+',
            rf'\g<1>{genes["sl_atr_mul"]:.3f}',
            result,
            count=1,
        )

    # Patch TP ATR multiplier
    if "tp_atr_mul" in genes:
        result = re.sub(
            r'(float tp_atr_mult = input\.float\(\s*\n?\s*defval\s*=\s*)[\d.]+',
            rf'\g<1>{genes["tp_atr_mul"]:.3f}',
            result,
            count=1,
        )

    # Patch trailing ATR multiplier
    if "trail_atr" in genes:
        result = re.sub(
            r'(float trail_atr_mult = input\.float\(\s*\n?\s*defval\s*=\s*)[\d.]+',
            rf'\g<1>{genes["trail_atr"]:.3f}',
            result,
            count=1,
        )

    # Patch vol mult
    if "vol_mult" in genes:
        result = re.sub(
            r'(float vol_mult = input\.float\(\s*\n?\s*defval\s*=\s*)[\d.]+',
            rf'\g<1>{genes["vol_mult"]:.3f}',
            result,
            count=1,
        )

    # Patch ATR min pct (from body_atr_mul mapping)
    if "body_atr_mul" in genes:
        # Map body_atr_mul to a reasonable atr_min_pct
        atr_min = max(0.1, min(1.0, genes["body_atr_mul"] * 1.5))
        result = re.sub(
            r'(float atr_min_pct = input\.float\(\s*\n?\s*defval\s*=\s*)[\d.]+',
            rf'\g<1>{atr_min:.2f}',
            result,
            count=1,
        )

    # Patch use_trailing (from use_trail gene)
    if "use_trail" in genes:
        use_trail_val = "true" if genes["use_trail"] >= 0.5 else "false"
        result = re.sub(
            r'(bool use_trailing = input\.bool\(\s*\n?\s*defval\s*=\s*)\w+',
            rf'\g<1>{use_trail_val}',
            result,
            count=1,
        )

    # Add GA metadata comment at top
    meta = f"""// ============================================================
// GA-OPTIMIZED PARAMETERS
// Generated from cross-algo GA optimization
// Symbol: {symbol}
// IS Return: +{genes.get('_is_return', 0):.2f}% | OOS Return: +{genes.get('_oos_return', 0):.2f}%
// Fitness: {genes.get('_fitness', 0):.4f} | Max DD: {genes.get('_max_dd', 0):.2f}%
// ============================================================
// Optimized Genes:
"""
    for k, v in genes.items():
        if not k.startswith("_"):
            meta += f"//   {k:15s} = {v}\n"
    meta += "// ============================================================\n\n"

    # Insert metadata after version line
    result = re.sub(
        r'(//@version=6\n)',
        rf'\g<1>{meta}',
        result,
        count=1,
    )

    # Ensure barstate.isconfirmed is used for entry logic (prevent repainting)
    if "barstate.isconfirmed" not in result:
        # Add a barstate check wrapper around the entry conditions
        result = re.sub(
            r'(bool long_entry\s*=)',
            r'bool _confirmed = barstate.isconfirmed\n\g<1>',
            result,
            count=1,
        )
        result = re.sub(
            r'(bool short_entry\s*=)',
            r'bool _confirmed = barstate.isconfirmed\n\g<1>',
            result,
            count=1,
        )
        # If both replaced, we have duplicate _confirmed — fix by keeping only first
        result = re.sub(
            r'(bool _confirmed = barstate\.isconfirmed\n)(.*\n)(bool _confirmed = barstate\.isconfirmed\n)',
            r'\g<1>\g<2>',
            result,
            count=1,
        )
        # Add _confirmed to entry conditions
        result = re.sub(
            r'(bool long_entry\s*=\s*)([^\n]+)',
            r'\g<1>_confirmed and (\g<2>)',
            result,
            count=1,
        )
        result = re.sub(
            r'(bool short_entry\s*=\s*)([^\n]+)',
            r'\g<1>_confirmed and (\g<2>)',
            result,
            count=1,
        )

    # Ensure lookahead=barmerge.lookahead_off on any request.security calls
    if "request.security" in result and "lookahead=barmerge.lookahead_off" not in result:
        result = re.sub(
            r'(request\.security\([^)]+)\)',
            r'\g<1>, lookahead=barmerge.lookahead_off)',
            result,
        )

    return result


def main():
    ga_path = Path(__file__).parent / "optimizer_results" / "hypeusdt_1m_crossalgo_ga_results.json"
    template_path = Path("G:/Downloads_Sortiert_2026-05-20/pine/HYPE_Pionex_Final.pine")
    output_dir = Path(__file__).parent / "generated_pines"
    output_dir.mkdir(parents=True, exist_ok=True)

    ga = load_ga_results(ga_path)
    top3 = ga.get("top3", [])

    if not top3:
        print("[ERROR] No top3 results in GA file")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    for i, ind in enumerate(top3[:3], 1):
        genes = dict(ind["genes"])
        genes["_fitness"] = ind.get("fitness", 0)
        genes["_is_return"] = ind.get("is_return", 0)
        genes["_oos_return"] = ind.get("oos_return", 0)
        genes["_max_dd"] = ind.get("max_drawdown", 0)

        patched = patch_template(template, genes, symbol="HYPEUSDT")
        out_path = output_dir / f"Top{i}_HYPEUSDT_GA_CrossAlgo_Optimized.pine"
        out_path.write_text(patched, encoding="utf-8")
        print(f"[SAVED] {out_path}")
        print(f"  Fitness: {ind['fitness']:.4f} | IS: {ind['is_return']:+.2f}% | OOS: {ind['oos_return']:+.2f}%")

    print(f"\n[DONE] {len(top3[:3])} Pine Script files generated in {output_dir}")


if __name__ == "__main__":
    main()
