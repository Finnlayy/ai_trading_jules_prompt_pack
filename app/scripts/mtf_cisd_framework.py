#!/usr/bin/env python3
# ============================================================================
# MTF CISD + OB/FVG Backtesting Framework
# ============================================================================
# Features:
#   - Binance Daten-Loader (CCXT / CSV / API)
#   - Walk-Forward-Optimierung
#   - Monte-Carlo-Validierung
#   - Vollständige Performance-Metriken
#
# Autor: AI-Assistent
# Datum: 2026-04-28
# ============================================================================

import pandas as pd
import numpy as np
import secrets
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# KONFIGURATION
# ============================================================================

@dataclass
class StrategyConfig:
    """Alle Parameter der MTF CISD + OB/FVG Strategie"""
    min_alignment: int = 1
    min_conf: int = 7
    sl_atr_mul: float = 0.6
    tp_atr_mul: float = 1.5
    ob_atr_mul: float = 1.6
    ob_pivot: int = 6
    max_ob_boxes: int = 25
    use_trail: bool = False
    trail_atr: float = 1.2
    use_max_dd: bool = True
    max_dd_pct: float = 8.0
    use_max_bars: bool = False
    max_bars_held: int = 48
    use_daily: bool = True
    daily_lim: float = 3.0
    use_vol: bool = False
    vol_mult: float = 1.05
    vol_period: int = 20
    use_ema_filter: bool = True
    use_rsi_filter: bool = False
    rsi_ob: float = 78.0
    rsi_os: float = 22.0
    use_atr_filter: bool = False
    atr_min_pct: float = 0.15
    allow_short: bool = False
    position_size_pct: float = 33.0
    initial_capital: float = 100.0
    en_h4: bool = True
    en_h1: bool = True
    en_m15: bool = True
    en_m5: bool = False


# ============================================================================
# BINANCE DATEN-LADER
# ============================================================================

class BinanceDataLoader:
    """
    Lädt OHLCV-Daten von Binance.

    OPTION A: CCXT (empfohlen)
        pip install ccxt
        df = BinanceDataLoader.from_ccxt('ETH/USDT', '5m', limit=1000)

    OPTION B: CSV (du lädst die Daten herunter)
        df = BinanceDataLoader.from_csv('eth_usdt_5min.csv')

    OPTION C: Direkte Binance API
        df = BinanceDataLoader.from_api('ETHUSDT', '5m', start_time, end_time)
    """

    @staticmethod
    def from_ccxt(symbol: str = 'ETH/USDT', timeframe: str = '5m', 
                  since: Optional[int] = None, limit: int = 1000) -> pd.DataFrame:
        """Nutzt CCXT für Live-Daten von Binance"""
        try:
            import ccxt
            exchange = ccxt.binance({'enableRateLimit': True})
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except ImportError:
            print("[ERROR] CCXT nicht installiert. Nutze: pip install ccxt")
            return pd.DataFrame()

    @staticmethod
    def from_csv(filepath: str) -> pd.DataFrame:
        """Lädt Binance-Daten aus CSV"""
        df = pd.read_csv(filepath, parse_dates=['timestamp'], index_col='timestamp')
        return df[['open', 'high', 'low', 'close', 'volume']]

    @staticmethod
    def from_api(symbol: str = 'ETHUSDT', interval: str = '5m',
                 start_time: Optional[int] = None, 
                 end_time: Optional[int] = None) -> pd.DataFrame:
        """Direkte Binance API (ohne CCXT)"""
        import requests
        url = 'https://api.binance.com/api/v3/klines'
        params = {'symbol': symbol, 'interval': interval, 'limit': 1000}
        if start_time: params['startTime'] = start_time
        if end_time: params['endTime'] = end_time

        response = requests.get(url, params=params, timeout=30)
        data = response.json()

        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df


# ============================================================================
# CISD ENGINE
# ============================================================================

def compute_cisd(open_vals, close_vals, high_vals, low_vals):
    """Change in State of Delivery"""
    n = len(open_vals)
    state = np.zeros(n, dtype=int)
    bull_cisd = np.zeros(n, dtype=bool)
    bear_cisd = np.zeros(n, dtype=bool)
    current_state = 0

    for i in range(1, n):
        is_bull = close_vals[i] > open_vals[i]
        is_bear = close_vals[i] < open_vals[i]

        if is_bear and current_state != -1:
            if close_vals[i] < open_vals[i-1]:
                if not (high_vals[i] < high_vals[i-1] and low_vals[i] > low_vals[i-1]):
                    current_state = -1
                    bear_cisd[i] = True

        if is_bull and current_state != 1:
            if close_vals[i] > open_vals[i-1]:
                if not (high_vals[i] < high_vals[i-1] and low_vals[i] > low_vals[i-1]):
                    current_state = 1
                    bull_cisd[i] = True

        state[i] = current_state

    return state, bull_cisd, bear_cisd


# ============================================================================
# BACKTEST ENGINE
# ============================================================================

def run_backtest(df: pd.DataFrame, cfg: StrategyConfig):
    """Vollständiger Backtest"""
    n = len(df)
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    v = df['volume'].values

    # Indikatoren
    atr = pd.Series(h - l).rolling(14, min_periods=1).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values
    delta = pd.Series(c).diff()
    gain = delta.where(delta > 0, 0).rolling(14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).values
    vol_sma = pd.Series(v).rolling(cfg.vol_period, min_periods=1).mean().values

    # MTF CISD
    state_local, bull_local, bear_local = compute_cisd(o, c, h, l)
    state_h4 = np.roll(state_local, 12); state_h4[:12] = 0
    state_h1 = np.roll(state_local, 3); state_h1[:3] = 0
    state_m15 = np.roll(state_local, 1); state_m15[:1] = 0

    bull_count = (cfg.en_h4 & (state_h4 == 1)).astype(int) +                  (cfg.en_h1 & (state_h1 == 1)).astype(int) +                  (cfg.en_m15 & (state_m15 == 1)).astype(int) +                  (cfg.en_m5 & (state_local == 1)).astype(int)

    bear_count = (cfg.en_h4 & (state_h4 == -1)).astype(int) +                  (cfg.en_h1 & (state_h1 == -1)).astype(int) +                  (cfg.en_m15 & (state_m15 == -1)).astype(int) +                  (cfg.en_m5 & (state_local == -1)).astype(int)

    active_tfs = cfg.en_h4 + cfg.en_h1 + cfg.en_m15 + cfg.en_m5
    bull_aligned = bull_count >= cfg.min_alignment
    bear_aligned = bear_count >= cfg.min_alignment

    # Confidence
    bull_conf = ((bull_count == active_tfs) & (active_tfs >= 3)).astype(int) * 4 +                 ((bull_count >= cfg.min_alignment) & (bull_count < active_tfs)).astype(int) * 2 +                 bull_local.astype(int) * 3 + ((c > o) & ((c - o) > atr * 0.5)).astype(int) * 2

    bear_conf = ((bear_count == active_tfs) & (active_tfs >= 3)).astype(int) * 4 +                 ((bear_count >= cfg.min_alignment) & (bear_count < active_tfs)).astype(int) * 2 +                 bear_local.astype(int) * 3 + ((o > c) & ((o - c) > atr * 0.5)).astype(int) * 2

    # Filter
    ema_f_long = ~cfg.use_ema_filter | (c > ema200)
    ema_f_short = ~cfg.use_ema_filter | (c < ema200)
    rsi_f_long = ~cfg.use_rsi_filter | (rsi < cfg.rsi_ob)
    rsi_f_short = ~cfg.use_rsi_filter | (rsi > cfg.rsi_os)
    atr_f = ~cfg.use_atr_filter | ((atr / c) * 100 >= cfg.atr_min_pct)
    vol_f = ~cfg.use_vol | (v > vol_sma * cfg.vol_mult)

    all_f_long = ema_f_long & rsi_f_long & atr_f & vol_f
    all_f_short = ema_f_short & rsi_f_short & atr_f & vol_f

    # Signale
    long_sig = bull_aligned & bull_local & (bull_conf >= cfg.min_conf) & all_f_long
    short_sig = cfg.allow_short & bear_aligned & bear_local & (bear_conf >= cfg.min_conf) & all_f_short

    # Backtest Loop
    equity = cfg.initial_capital
    position = 0; entry_price = 0.0; sl_price = 0.0; tp_price = 0.0
    trail_price = 0.0; bars_in_pos = 0; pending_side = 0; qty = 0.0
    daily_start = c[0]; equity_peak = equity

    trades = []; equity_history = [equity]

    for i in range(200, n):
        if i > 0 and df.index[i].date() != df.index[i-1].date():
            daily_start = c[i]

        equity_peak = max(equity_peak, equity)
        dd_pct = ((equity_peak - equity) / equity_peak) * 100
        daily_pnl = ((c[i] - daily_start) / daily_start) * 100

        risk_ok = True
        if cfg.use_daily and daily_pnl <= -cfg.daily_lim: risk_ok = False
        if cfg.use_max_dd and dd_pct >= cfg.max_dd_pct: risk_ok = False

        long_sl = c[i] - atr[i] * cfg.sl_atr_mul
        long_tp = c[i] + atr[i] * cfg.tp_atr_mul
        short_sl = c[i] + atr[i] * cfg.sl_atr_mul
        short_tp = c[i] - atr[i] * cfg.tp_atr_mul

        if position == 1 and cfg.use_trail and trail_price > 0:
            trail_price = max(trail_price, h[i] - atr[i] * cfg.trail_atr)
        if position == -1 and cfg.use_trail and trail_price > 0:
            trail_price = min(trail_price, l[i] + atr[i] * cfg.trail_atr)

        als = max(sl_price, trail_price) if (cfg.use_trail and trail_price > 0) else sl_price
        ass = min(sl_price, trail_price) if (cfg.use_trail and trail_price > 0) else sl_price

        # EXIT
        ex = False; er = ""
        if position == 1:
            bars_in_pos += 1
            if l[i] <= als: xp = als; ex = True; er = "sl"
            elif h[i] >= tp_price: xp = tp_price; ex = True; er = "tp"
            elif cfg.use_max_bars and bars_in_pos >= cfg.max_bars_held: xp = c[i]; ex = True; er = "max_bars"
            elif not bull_aligned[i]: xp = c[i]; ex = True; er = "forced"
            elif not risk_ok: xp = c[i]; ex = True; er = "daily"
            if ex:
                pnl = (xp - entry_price) * qty; equity += pnl
                trades.append({'side': 'long', 'entry': entry_price, 'exit': xp, 'pnl': pnl, 
                              'pnl_pct': (xp/entry_price - 1)*100, 'bars': bars_in_pos, 'reason': er})
                position = 0; bars_in_pos = 0; pending_side = 0
        elif position == -1:
            bars_in_pos += 1
            if h[i] >= ass: xp = ass; ex = True; er = "sl"
            elif l[i] <= tp_price: xp = tp_price; ex = True; er = "tp"
            elif cfg.use_max_bars and bars_in_pos >= cfg.max_bars_held: xp = c[i]; ex = True; er = "max_bars"
            elif not bear_aligned[i]: xp = c[i]; ex = True; er = "forced"
            elif not risk_ok: xp = c[i]; ex = True; er = "daily"
            if ex:
                pnl = (entry_price - xp) * qty; equity += pnl
                trades.append({'side': 'short', 'entry': entry_price, 'exit': xp, 'pnl': pnl,
                              'pnl_pct': (entry_price/xp - 1)*100, 'bars': bars_in_pos, 'reason': er})
                position = 0; bars_in_pos = 0; pending_side = 0

        # ENTRY
        if position == 0 and risk_ok and pending_side == 0:
            qty = (equity * cfg.position_size_pct / 100) / c[i] if c[i] > 0 else 0
            if long_sig[i]:
                position = 1; entry_price = c[i]; sl_price = long_sl; tp_price = long_tp
                trail_price = long_sl if cfg.use_trail else 0; pending_side = 1; bars_in_pos = 0
            elif short_sig[i] and cfg.allow_short:
                position = -1; entry_price = c[i]; sl_price = short_sl; tp_price = short_tp
                trail_price = short_sl if cfg.use_trail else 0; pending_side = -1; bars_in_pos = 0

        equity_history.append(equity)

    if not trades:
        return {'error': 'Keine Trades'}

    tdf = pd.DataFrame(trades)
    wins = len(tdf[tdf['pnl'] > 0]); losses = len(tdf[tdf['pnl'] < 0])
    wr = wins / len(tdf) * 100 if len(tdf) > 0 else 0
    aw = tdf[tdf['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
    al = tdf[tdf['pnl'] < 0]['pnl'].mean() if losses > 0 else 0
    pf = abs(tdf[tdf['pnl'] > 0]['pnl'].sum() / tdf[tdf['pnl'] < 0]['pnl'].sum()) if losses > 0 else float('inf')

    eqs = pd.Series(equity_history)
    ret = eqs.pct_change().dropna()
    sharpe = (ret.mean() * 252 * 288) / (ret.std() * np.sqrt(252 * 288)) if ret.std() > 0 else 0

    cummax = eqs.cummax()
    dd = (eqs - cummax) / cummax * 100
    mdd = dd.min()

    downside = ret[ret < 0]
    sortino = (ret.mean() * 252 * 288) / (downside.std() * np.sqrt(252 * 288)) if len(downside) > 0 and downside.std() > 0 else 0
    total_ret = (equity / cfg.initial_capital - 1) * 100
    calmar = total_ret / abs(mdd) if mdd != 0 else 0

    return {
        'trades': len(tdf), 'wins': wins, 'losses': losses,
        'win_rate': wr, 'avg_win': aw, 'avg_loss': al,
        'profit_factor': pf, 'final_equity': equity,
        'return_pct': total_ret, 'max_dd': mdd,
        'sharpe': sharpe, 'sortino': sortino, 'calmar': calmar,
        'avg_bars': tdf['bars'].mean(),
        'equity': eqs, 'drawdown': dd, 'trades_df': tdf,
        'returns': ret
    }


# ============================================================================
# WALK-FORWARD OPTIMIZER
# ============================================================================

class WalkForwardOptimizer:
    def __init__(self, train_size: int = 2000, test_size: int = 500, step_size: int = 500):
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size

    def optimize_window(self, df: pd.DataFrame, param_grid: List[Dict]):
        n = len(df)
        window_results = []

        for start in range(0, n - self.train_size - self.test_size + 1, self.step_size):
            train_end = start + self.train_size
            test_end = train_end + self.test_size

            df_train = df.iloc[start:train_end]
            df_test = df.iloc[train_end:test_end]

            print(f"\n[WINDOW] {start}-{test_end}: Train {start}-{train_end}, Test {train_end}-{test_end}")

            best_train = None
            best_train_score = -np.inf

            for params in param_grid:
                cfg = StrategyConfig(**params)
                res = run_backtest(df_train, cfg)

                if 'error' in res or res['trades'] < 5:
                    continue

                score = res['sharpe'] * res['profit_factor'] / max(abs(res['max_dd']), 0.1)

                if score > best_train_score:
                    best_train_score = score
                    best_train = (params, res)

            if best_train is None:
                continue

            best_params, train_res = best_train
            cfg_test = StrategyConfig(**best_params)
            test_res = run_backtest(df_test, cfg_test)

            if 'error' in test_res:
                continue

            robustness = min(train_res['sharpe'], test_res['sharpe']) *                         min(train_res['profit_factor'], test_res['profit_factor']) /                         max(abs(test_res['max_dd']), 0.1)

            window_results.append({
                'window_start': start,
                'window_end': test_end,
                'params': best_params,
                'train_return': train_res['return_pct'],
                'test_return': test_res['return_pct'],
                'train_sharpe': train_res['sharpe'],
                'test_sharpe': test_res['sharpe'],
                'train_pf': train_res['profit_factor'],
                'test_pf': test_res['profit_factor'],
                'train_dd': train_res['max_dd'],
                'test_dd': test_res['max_dd'],
                'train_trades': train_res['trades'],
                'test_trades': test_res['trades'],
                'robustness': robustness
            })

            print(f"   [TRAIN] Return={train_res['return_pct']:.1f}%, Sharpe={train_res['sharpe']:.2f}")
            print(f"   [TEST]  Return={test_res['return_pct']:.1f}%, Sharpe={test_res['sharpe']:.2f}")
            print(f"   Robustness: {robustness:.2f}")

        return window_results


# ============================================================================
# MONTE CARLO VALIDATOR
# ============================================================================

class MonteCarloValidator:
    def __init__(self, n_simulations: int = 2000):
        self.n_simulations = n_simulations
        self.rng = np.random.default_rng(secrets.randbits(128))

    def run(self, trades_df: pd.DataFrame, initial_capital: float = 100.0):
        trades = trades_df['pnl'].values
        n_trades = len(trades)

        if n_trades == 0:
            return {'error': 'Keine Trades'}

        final_equities = []
        max_drawdowns = []
        sharpe_ratios = []

        for _ in range(self.n_simulations):
            sampled_trades = self.rng.choice(trades, size=n_trades, replace=True)

            equity = initial_capital
            equity_curve = [equity]

            for pnl in sampled_trades:
                equity += pnl
                equity_curve.append(equity)

            eqs = pd.Series(equity_curve)
            ret = eqs.pct_change().dropna()
            sharpe = (ret.mean() * 252 * 288) / (ret.std() * np.sqrt(252 * 288)) if ret.std() > 0 else 0

            cummax = eqs.cummax()
            dd = (eqs - cummax) / cummax * 100
            mdd = dd.min()

            final_equities.append(equity)
            max_drawdowns.append(mdd)
            sharpe_ratios.append(sharpe)

        final_equities = np.array(final_equities)
        max_drawdowns = np.array(max_drawdowns)
        sharpe_ratios = np.array(sharpe_ratios)

        return {
            'final_equity_mean': final_equities.mean(),
            'final_equity_std': final_equities.std(),
            'final_equity_5pct': np.percentile(final_equities, 5),
            'final_equity_95pct': np.percentile(final_equities, 95),
            'final_equity_median': np.median(final_equities),
            'max_dd_mean': max_drawdowns.mean(),
            'max_dd_5pct': np.percentile(max_drawdowns, 5),
            'max_dd_95pct': np.percentile(max_drawdowns, 95),
            'sharpe_mean': sharpe_ratios.mean(),
            'sharpe_5pct': np.percentile(sharpe_ratios, 5),
            'sharpe_95pct': np.percentile(sharpe_ratios, 95),
            'probability_profit': (final_equities > initial_capital).mean() * 100,
            'probability_ruin': (final_equities < initial_capital * 0.5).mean() * 100,
            'all_equities': final_equities,
            'all_drawdowns': max_drawdowns,
            'all_sharpes': sharpe_ratios
        }


# ============================================================================
# HAUPTPROGRAMM
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("MTF CISD + OB/FVG — Backtesting Framework")
    print("=" * 70)

    # 1. DATEN LADEN
    # Option A: Echte Binance-Daten via CCXT
    # df = BinanceDataLoader.from_ccxt('ETH/USDT', '5m', limit=1000)

    # Option B: CSV
    # df = BinanceDataLoader.from_csv('eth_usdt_5min.csv')

    # Option C: Direkte API
    # df = BinanceDataLoader.from_api('ETHUSDT', '5m')

    # Option D: Synthetische Testdaten
    print("\n[GEN] Generiere Testdaten...")
    rng = np.random.default_rng(secrets.randbits(128))
    n = 3000
    dates = pd.date_range('2025-01-01', periods=n, freq='5min')
    returns = rng.normal(0.0001, 0.008, n)
    close = 3200 * np.exp(np.cumsum(returns))
    df = pd.DataFrame({
        'open': close * (1 + rng.normal(0, 0.003, n)),
        'high': close * (1 + abs(rng.normal(0, 0.005, n))),
        'low': close * (1 - abs(rng.normal(0, 0.005, n))),
        'close': close,
        'volume': rng.lognormal(10, 0.5, n)
    }, index=dates)

    # 2. BACKTEST
    cfg = StrategyConfig()
    res = run_backtest(df, cfg)

    if 'error' not in res:
        print(f"\nBACKTEST ERGEBNISSE:")
        print(f"   Trades: {res['trades']} | Win Rate: {res['win_rate']:.1f}%")
        print(f"   Return: {res['return_pct']:.2f}% | Max DD: {res['max_dd']:.2f}%")
        print(f"   Sharpe: {res['sharpe']:.2f} | Profit Factor: {res['profit_factor']:.2f}")

        # 3. MONTE CARLO
        print(f"\nMONTE CARLO Simulation...")
        mc = MonteCarloValidator(n_simulations=1000)
        mc_res = mc.run(res['trades_df'])

        print(f"   Profit-Wahrscheinlichkeit: {mc_res['probability_profit']:.1f}%")
        print(f"   Ruin-Wahrscheinlichkeit: {mc_res['probability_ruin']:.1f}%")
        print(f"   Ø Endkapital: ${mc_res['final_equity_mean']:.2f}")
    else:
        print(f"[ERROR] Fehler: {res['error']}")
