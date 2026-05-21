#!/usr/bin/env python3
"""
BTCUSDT 15m Backtest Runner
Downloads historical data from Binance and runs MTF CISD backtest.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import time
import pandas as pd
from datetime import datetime, timedelta
from mtf_cisd_framework import BinanceDataLoader, StrategyConfig, run_backtest, MonteCarloValidator


def download_btc_15m(months: int = 4) -> pd.DataFrame:
    """Download BTCUSDT 15m data from Binance with pagination."""
    symbol = "BTCUSDT"
    interval = "15m"
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=30 * months)).timestamp() * 1000)

    all_data = []
    current_start = start_time

    print(f"[DOWNLOAD] {symbol} {interval} from {datetime.fromtimestamp(start_time/1000)} to {datetime.fromtimestamp(end_time/1000)}")

    while current_start < end_time:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "limit": 1000
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            all_data.extend(data)
            last_open_time = data[-1][0]
            current_start = last_open_time + 1

            print(f"   Fetched {len(data)} candles. Total: {len(all_data)}")
            time.sleep(0.1)  # Rate limit politeness

        except Exception as e:
            print(f"   Error: {e}")
            time.sleep(1)
            continue

    if not all_data:
        raise ValueError("No data downloaded")

    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

    print(f"[OK] Downloaded {len(df)} candles ({df.index[0]} -> {df.index[-1]})")
    return df


def main():
    print("=" * 70)
    print("BTCUSDT 15m — MTF CISD Backtest")
    print("=" * 70)

    # 1. Download data
    try:
        df = download_btc_15m(months=4)
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        print("   Falling back to direct API (last 1000 candles)...")
        df = BinanceDataLoader.from_api('BTCUSDT', '15m')

    if len(df) < 500:
        print("[ERROR] Not enough data for backtest")
        return

    # 2. Run backtest
    cfg = StrategyConfig(
        min_alignment=2,
        min_conf=6,
        sl_atr_mul=1.2,
        tp_atr_mul=2.4,
        use_trail=True,
        trail_atr=1.0,
        use_max_dd=True,
        max_dd_pct=10.0,
        use_daily=True,
        daily_lim=3.0,
        position_size_pct=10.0,
        initial_capital=1000.0,
        en_h4=True,
        en_h1=True,
        en_m15=True,
        en_m5=False,
        allow_short=False
    )

    print("\n[RUN] Running backtest...")
    res = run_backtest(df, cfg)

    if 'error' in res:
        print(f"[ERROR] Backtest error: {res['error']}")
        return

    # 3. Results
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print(f"   Trades:        {res['trades']}")
    print(f"   Wins:          {res['wins']} | Losses: {res['losses']}")
    print(f"   Win Rate:      {res['win_rate']:.1f}%")
    print(f"   Avg Win:       ${res['avg_win']:.2f}")
    print(f"   Avg Loss:      ${res['avg_loss']:.2f}")
    print(f"   Profit Factor: {res['profit_factor']:.2f}")
    print(f"   Final Equity:  ${res['final_equity']:.2f}")
    print(f"   Return:        {res['return_pct']:.2f}%")
    print(f"   Max Drawdown:  {res['max_dd']:.2f}%")
    print(f"   Sharpe:        {res['sharpe']:.2f}")
    print(f"   Sortino:       {res['sortino']:.2f}")
    print(f"   Calmar:        {res['calmar']:.2f}")
    print(f"   Avg Bars Held: {res['avg_bars']:.1f}")

    # 4. Monte Carlo
    print("\nMONTE CARLO SIMULATION (2000 runs)...")
    mc = MonteCarloValidator(n_simulations=2000)
    mc_res = mc.run(res['trades_df'], initial_capital=cfg.initial_capital)

    print(f"   Profit Probability:    {mc_res['probability_profit']:.1f}%")
    print(f"   Ruin Probability:      {mc_res['probability_ruin']:.1f}%")
    print(f"   Mean Final Equity:     ${mc_res['final_equity_mean']:.2f}")
    print(f"   Median Final Equity:   ${mc_res['final_equity_median']:.2f}")
    print(f"   5% VaR Equity:         ${mc_res['final_equity_5pct']:.2f}")
    print(f"   95% VaR Equity:        ${mc_res['final_equity_95pct']:.2f}")
    print(f"   Mean Max DD:           {mc_res['max_dd_mean']:.2f}%")
    print(f"   5% Max DD:             {mc_res['max_dd_5pct']:.2f}%")
    print(f"   95% Max DD:            {mc_res['max_dd_95pct']:.2f}%")

    # 5. Save results
    os.makedirs('backtest_results', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    res['trades_df'].to_csv(f'backtest_results/btc_15m_trades_{timestamp}.csv', index=False)
    print(f"\n[SAVED] Trades saved to: backtest_results/btc_15m_trades_{timestamp}.csv")

    print("\n" + "=" * 70)
    print("[DONE] Backtest complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
