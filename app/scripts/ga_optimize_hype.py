#!/usr/bin/env python3
"""
GA Optimization for HYPEUSDT 1m using real Bybit data.
Integrates genetic_optimizer logic with hypeusdt_1m_backtest_v23 engine.
"""

from __future__ import annotations

import json
import math
import random
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

# Import the backtest engine
import sys
sys.path.insert(0, str(Path(__file__).parent))
from hypeusdt_1m_backtest_v23 import (
    fetch_1m_klines, load_cached_1m_klines, backtest,
    Params, SYMBOL, Candle
)

# ─── GA CONFIG ────────────────────────────────────────────────────────────────

GA_CONFIG = {
    "population_size":   30,
    "n_generations":     50,
    "elite_count":       3,
    "mutation_rate":     0.05,
    "mutation_strength": 0.40,
    "crossover_threshold": 0.20,
    "random_seed":       42,
}

# Parameter search space: (min, max, type)
PARAM_SPACE = {
    "min_conf":      (5,   20,  "int"),
    "sl_atr_mul":    (0.5, 3.0, "float"),
    "tp_atr_mul":    (1.0, 8.0, "float"),
    "ob_atr_mul":    (0.5, 3.0, "float"),
    "ob_pivot":      (2,   10,  "int"),
    "w_align_full":  (1,   6,   "int"),
    "w_align_part":  (0,   4,   "int"),
    "w_cisd":        (1,   5,   "int"),
    "w_ob_touch":    (0,   5,   "int"),
    "w_fvg_touch":   (0,   5,   "int"),
    "w_vol_score":   (0,   4,   "int"),
    "w_body_score":  (0,   4,   "int"),
    "body_atr_mul":  (0.1, 1.0, "float"),
    "trail_atr":     (0.5, 3.0, "float"),
    "vol_mult":      (0.8, 2.0, "float"),
    "max_dd_pct":    (3.0, 20.0,"float"),
    "risk_per_trade":(0.5, 5.0, "float"),
}

DEFAULT_PARAMS = {
    "tf_h4": 48, "tf_h1": 12, "tf_m15": 3, "tf_m5": 1,
    "en_h4": True, "en_h1": True, "en_m15": True, "en_m5": False,
    "min_alignment": 3, "max_ob_boxes": 25, "max_fvg_boxes": 25,
    "use_trail": False, "use_max_dd": True, "use_max_bars": False,
    "max_bars_held": 48, "qty_step": 0.001, "use_vol": True,
    "vol_period": 20, "use_time": True, "start_time": 1530,
    "end_time": 2200, "session_timezone": "America/New_York",
    "warmup_bars": 50, "use_daily": True, "daily_lim": 3.0,
    "use_ema_filter": True, "ema_len": 200, "use_rsi_filter": True,
    "rsi_len": 14, "rsi_ob": 78.0, "rsi_os": 22.0,
    "use_atr_filter": True, "atr_min_pct": 0.15, "allow_short": False,
}


@dataclass
class Individual:
    genes: Dict[str, float]
    fitness: float = -np.inf
    net_profit: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    n_trades: int = 0
    return_pct: float = 0.0
    profit_factor: float = 0.0
    generation: int = 0

    def to_dict(self) -> Dict:
        return {
            "genes": self.genes,
            "fitness": round(self.fitness, 4),
            "net_profit": round(self.net_profit, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "win_rate": round(self.win_rate, 2),
            "n_trades": self.n_trades,
            "return_pct": round(self.return_pct, 4),
            "profit_factor": round(self.profit_factor, 4),
            "generation": self.generation,
        }


def genes_to_params(genes: Dict[str, float]) -> Params:
    """Convert GA genes to Strategy Params."""
    kwargs = dict(DEFAULT_PARAMS)
    for k, v in genes.items():
        kwargs[k] = v
    return Params(**kwargs)


def run_backtest_on_data(candles: List[Candle], genes: Dict[str, float]) -> Dict:
    """Run backtest with given genes on cached data."""
    p = genes_to_params(genes)
    try:
        result = backtest(candles, p)
        return result
    except Exception as e:
        return {
            "net_profit": -100.0, "return_pct": -100.0,
            "max_drawdown_pct": 100.0, "win_rate_pct": 0.0,
            "trades": 0, "profit_factor": 0.0,
        }


def fitness(result: Dict) -> float:
    """Fitness = return_pct * win_rate_factor / (1 + max_dd * 0.1) with trade count penalty."""
    trades = result.get("trades", 0)
    if trades < 3:
        return -100.0

    ret = result.get("return_pct", -100.0)
    wr = result.get("win_rate_pct", 0.0)
    dd = result.get("max_drawdown_pct", 100.0)
    pf = result.get("profit_factor", 0.0)

    if ret <= 0 or pf < 1.0:
        return -50.0 + ret

    win_factor = max(0.3, wr / 50.0)
    dd_penalty = 1.0 + dd * 0.05
    trade_bonus = min(2.0, trades / 20.0)
    pf_bonus = min(3.0, pf / 2.0)

    return (ret * win_factor * trade_bonus * pf_bonus) / dd_penalty


class GeneticOptimizer:
    def __init__(self, candles: List[Candle], config: Dict, seed: int = 42):
        self.candles = candles
        self.config = config
        self.rng = random.Random(seed)
        self.population: List[Individual] = []
        self.hall_of_fame: List[Individual] = []
        self.generation_stats: List[Dict] = []

    def _random_genes(self) -> Dict[str, float]:
        genes = {}
        for name, (lo, hi, typ) in PARAM_SPACE.items():
            val = self.rng.uniform(lo, hi)
            genes[name] = int(round(val)) if typ == "int" else round(val, 3)
        return genes

    def _evaluate(self, ind: Individual) -> float:
        result = run_backtest_on_data(self.candles, ind.genes)
        ind.net_profit = result.get("net_profit", 0.0)
        ind.return_pct = result.get("return_pct", 0.0)
        ind.max_drawdown = result.get("max_drawdown_pct", 100.0)
        ind.win_rate = result.get("win_rate_pct", 0.0)
        ind.n_trades = result.get("trades", 0)
        ind.profit_factor = result.get("profit_factor", 0.0)
        ind.fitness = fitness(result)
        return ind.fitness

    def _crossover(self, p1: Individual, p2: Individual) -> Individual:
        child_genes = {}
        for name in PARAM_SPACE:
            if self.rng.random() < self.config["crossover_threshold"]:
                child_genes[name] = p2.genes[name]
            else:
                child_genes[name] = p1.genes[name]
        return Individual(genes=child_genes)

    def _mutate(self, ind: Individual) -> Individual:
        mutated = deepcopy(ind)
        for name, (lo, hi, typ) in PARAM_SPACE.items():
            if self.rng.random() < self.config["mutation_rate"]:
                current = mutated.genes[name]
                delta = abs(current) * self.config["mutation_strength"]
                new_val = current + self.rng.uniform(-delta, delta)
                new_val = max(lo, min(hi, new_val))
                mutated.genes[name] = int(round(new_val)) if typ == "int" else round(new_val, 3)
        return mutated

    def _select_parents(self) -> Tuple[Individual, Individual]:
        def tournament(k=3):
            candidates = self.rng.sample(self.population, min(k, len(self.population)))
            return max(candidates, key=lambda x: x.fitness)
        return tournament(), tournament()

    def run(self) -> List[Individual]:
        cfg = self.config
        pop_size = cfg["population_size"]
        n_gen = cfg["n_generations"]
        elite_n = cfg["elite_count"]

        print("=" * 70)
        print(f"  GA Optimization — HYPEUSDT 1m")
        print(f"  Pop: {pop_size} | Gen: {n_gen} | Elite: {elite_n}")
        print(f"  Data: {len(self.candles)} candles")
        print("=" * 70)

        # Initial population
        self.population = [Individual(genes=self._random_genes()) for _ in range(pop_size)]
        for ind in self.population:
            self._evaluate(ind)
        self.population.sort(key=lambda x: x.fitness, reverse=True)

        for gen in range(n_gen):
            new_pop = [deepcopy(ind) for ind in self.population[:elite_n]]
            for ind in new_pop:
                ind.generation = gen + 1

            while len(new_pop) < pop_size:
                p1, p2 = self._select_parents()
                child = self._crossover(p1, p2)
                child = self._mutate(child)
                child.generation = gen + 1
                self._evaluate(child)
                new_pop.append(child)

            self.population = sorted(new_pop, key=lambda x: x.fitness, reverse=True)

            best = self.population[0]
            avg_fit = np.mean([ind.fitness for ind in self.population])

            self.generation_stats.append({
                "generation": gen + 1,
                "best_fitness": round(best.fitness, 4),
                "best_return": round(best.return_pct, 4),
                "best_dd": round(best.max_drawdown, 2),
                "best_wr": round(best.win_rate, 1),
                "best_trades": best.n_trades,
                "avg_fitness": round(avg_fit, 4),
            })

            if (gen + 1) % 5 == 0 or gen == 0:
                print(f"  Gen {gen+1:3d}/{n_gen} | Best: {best.fitness:8.2f} | "
                      f"Ret: {best.return_pct:+6.2f}% | DD: {best.max_drawdown:5.1f}% | "
                      f"WR: {best.win_rate:4.1f}% | Trades: {best.n_trades}")

            # Update hall of fame
            for ind in self.population[:elite_n]:
                if len(self.hall_of_fame) < 3 or ind.fitness > min(x.fitness for x in self.hall_of_fame):
                    self.hall_of_fame.append(deepcopy(ind))
                    self.hall_of_fame.sort(key=lambda x: x.fitness, reverse=True)
                    self.hall_of_fame = self.hall_of_fame[:3]

        return self.hall_of_fame


def main():
    cache_dir = Path(__file__).parent / "data_cache"
    result_dir = Path(__file__).parent / "optimizer_results"
    result_dir.mkdir(parents=True, exist_ok=True)

    # Load or fetch data
    print("[LOAD] Fetching HYPEUSDT 1m data...")
    try:
        candles = load_cached_1m_klines(SYMBOL, 10000, cache_dir)
    except FileNotFoundError:
        candles = fetch_1m_klines(SYMBOL, 10000)

    print(f"[LOAD] {len(candles)} candles loaded")

    # Run GA
    optimizer = GeneticOptimizer(candles, GA_CONFIG, seed=GA_CONFIG["random_seed"])
    top3 = optimizer.run()

    # Results
    print("\n" + "=" * 70)
    print("  TOP 3 RESULTS")
    print("=" * 70)
    for i, ind in enumerate(top3):
        print(f"\n  Rank #{i+1}")
        print(f"  Fitness: {ind.fitness:.4f}")
        print(f"  Return:  {ind.return_pct:+.2f}%")
        print(f"  Max DD:  {ind.max_drawdown:.2f}%")
        print(f"  WinRate: {ind.win_rate:.1f}%")
        print(f"  Trades:  {ind.n_trades}")
        print(f"  PF:      {ind.profit_factor:.2f}")
        print(f"  Genes:")
        for k, v in ind.genes.items():
            print(f"    {k:15s} = {v}")

    # Save
    output = {
        "config": GA_CONFIG,
        "symbol": SYMBOL,
        "candles": len(candles),
        "top3": [ind.to_dict() for ind in top3],
        "generation_stats": optimizer.generation_stats,
    }

    out_path = result_dir / "hypeusdt_1m_ga_results.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\n[SAVED] {out_path}")

    print("\n" + "=" * 70)
    print("[DONE] GA Optimization complete")
    print("=" * 70)


if __name__ == "__main__":
    start = time.time()
    main()
    print(f"\nElapsed: {time.time() - start:.1f}s")
