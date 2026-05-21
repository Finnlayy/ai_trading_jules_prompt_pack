#!/usr/bin/env python3
import sys
sys.path.insert(0, 'scripts')

import requests
import time
import pandas as pd
from datetime import datetime, timedelta
from mtf_cisd_framework import StrategyConfig, run_backtest, compute_cisd
import numpy as np


def download_quick(symbol="BTCUSDT", interval="15m", limit=1000):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
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


def debug_signals(df, cfg):
    n = len(df)
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    v = df['volume'].values

    atr = pd.Series(h - l).rolling(14, min_periods=1).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values

    state_local, bull_local, bear_local = compute_cisd(o, c, h, l)
    state_h4 = np.roll(state_local, 12); state_h4[:12] = 0
    state_h1 = np.roll(state_local, 3); state_h1[:3] = 0
    state_m15 = np.roll(state_local, 1); state_m15[:1] = 0

    bull_count = (cfg.en_h4 & (state_h4 == 1)).astype(int) + \
                 (cfg.en_h1 & (state_h1 == 1)).astype(int) + \
                 (cfg.en_m15 & (state_m15 == 1)).astype(int) + \
                 (cfg.en_m5 & (state_local == 1)).astype(int)

    active_tfs = cfg.en_h4 + cfg.en_h1 + cfg.en_m15 + cfg.en_m5
    bull_aligned = bull_count >= cfg.min_alignment

    bull_conf = ((bull_count == active_tfs) & (active_tfs >= 3)).astype(int) * 4 + \
                ((bull_count >= cfg.min_alignment) & (bull_count < active_tfs)).astype(int) * 2 + \
                bull_local.astype(int) * 3 + ((c > o) & ((c - o) > atr * 0.5)).astype(int) * 2

    ema_f_long = ~cfg.use_ema_filter | (c > ema200)
    all_f_long = ema_f_long

    long_sig = bull_aligned & bull_local & (bull_conf >= cfg.min_conf) & all_f_long

    print(f"Total bars: {n}")
    print(f"Bull aligned count: {bull_aligned.sum()}")
    print(f"Bull CISD count: {bull_local.sum()}")
    print(f"Conf >= {cfg.min_conf} count: {(bull_conf >= cfg.min_conf).sum()}")
    print(f"EMA filter pass: {ema_f_long.sum()}")
    print(f"Long signals: {long_sig.sum()}")
    print(f"\nSample bull_conf values (last 20): {bull_conf[-20:]}")
    print(f"Sample alignment (last 20): {bull_count[-20:]}")
    print(f"Sample local state (last 20): {state_local[-20:]}")


if __name__ == "__main__":
    print("[DEBUG] Downloading BTCUSDT 15m data...")
    df = download_quick("BTCUSDT", "15m", 2000)
    print(f"[DEBUG] Got {len(df)} bars")

    cfg = StrategyConfig(
        min_alignment=1,
        min_conf=5,
        use_ema_filter=False,
        en_h4=True,
        en_h1=True,
        en_m15=True,
        en_m5=False
    )

    print("\n[DEBUG] Signal analysis:")
    debug_signals(df, cfg)

    print("\n[DEBUG] Running backtest with lenient config...")
    res = run_backtest(df, cfg)
    if 'error' in res:
        print(f"[ERROR] {res['error']}")
    else:
        print(f"Trades: {res['trades']}, Win Rate: {res['win_rate']:.1f}%, Return: {res['return_pct']:.2f}%")
