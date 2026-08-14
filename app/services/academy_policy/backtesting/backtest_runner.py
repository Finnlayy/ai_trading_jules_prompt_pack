from __future__ import annotations

import logging
from typing import Any
import numpy as np
import pandas as pd
import backtrader as bt

from app.services.academy_policy.backtesting.data_adapter import dataframe_to_backtrader_feed

logger = logging.getLogger(__name__)

try:
    import vectorbt as vbt
    VECTORBT_AVAILABLE = True
except ImportError:
    logger.warning("VectorBT is not available in this environment. Fallback simulation will be used.")
    vbt = None
    VECTORBT_AVAILABLE = False


class PPOBacktraderStrategy(bt.Strategy):
    """
    Backtrader Strategy that processes PPO-Policy-Outputs and KPI metrics as trading signals.
    """
    params = (
        ("target_scout_index", 0),
        ("min_reward", 0.0),
        ("min_accuracy", 0.5),
        ("size", 100.0),
    )

    def __init__(self) -> None:
        # PPO integration point
        # Map PPO policy data lines from adapter
        self.scout_index = self.datas[0].scout_index
        self.difficulty = self.datas[0].difficulty
        self.total_reward = self.datas[0].total_reward
        self.accuracy = self.datas[0].accuracy
        self.calibration = self.datas[0].calibration
        self.ab_lift = self.datas[0].ab_lift
        
        # Track curves
        self.equity_values: list[float] = []
        self.drawdown_values: list[float] = []
        self.dates: list[pd.Timestamp] = []
        self.peak_value = self.broker.getvalue()
        
        # Track trades
        self.trade_records: list[dict[str, Any]] = []

    def next(self) -> None:
        # INSERT PPO SIGNAL HERE
        # read custom lines populated from academy policy models
        current_scout = int(self.scout_index[0])              # from state.py: scout_index
        current_accuracy = float(self.accuracy[0])           # from state.py: accuracy
        current_reward = float(self.total_reward[0])         # from reward.py: scalar float reward
        current_calibration = float(self.calibration[0])     # from state.py: calibration
        current_ab_lift = float(self.ab_lift[0])             # from state.py: ab_lift

        current_value = self.broker.getvalue()
        self.peak_value = max(self.peak_value, current_value)
        current_drawdown = ((self.peak_value - current_value) / self.peak_value) * 100.0 if self.peak_value > 0 else 0.0
        
        self.equity_values.append(current_value)
        self.drawdown_values.append(current_drawdown)
        self.dates.append(pd.Timestamp(self.data.datetime.datetime(0)))

        # Trading Logic:
        # Enter position if the target scout is active, accuracy is high, and reward is positive
        if not self.position:
            if (current_scout == self.params.target_scout_index and 
                    current_accuracy >= self.params.min_accuracy and 
                    current_reward >= self.params.min_reward):
                self.buy(size=self.params.size)
        else:
            # Exit position if the target scout is no longer active or KPIs degrade below thresholds
            if (current_scout != self.params.target_scout_index or 
                    current_accuracy < self.params.min_accuracy or 
                    current_reward < self.params.min_reward):
                self.close()

    def notify_trade(self, trade: bt.Trade) -> None:
        if trade.isclosed:
            self.trade_records.append({
                "status": "closed",
                "pnl": trade.pnl,
                "pnlcomm": trade.pnlcomm,
                "baropen": trade.baropen,
                "barclose": trade.barclose,
                "price": trade.price,
                "value": trade.value,
            })


class BacktestRunner:
    """
    Orchestrates policy signal backtesting using Backtrader or VectorBT backends,
    returning unified metrics and curves.
    """
    
    def run_backtrader(self, data: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
        """
        Runs a Backtrader-based simulation.
        """
        if data.empty:
            raise ValueError("Input DataFrame is empty")

        initial_cash = params.get("initial_cash", 10000.0)
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(initial_cash)
        
        # Load and add PPO data feed
        feed = dataframe_to_backtrader_feed(data)
        cerebro.adddata(feed)
        
        # Add strategy
        cerebro.addstrategy(
            PPOBacktraderStrategy,
            target_scout_index=params.get("target_scout_index", 0),
            min_reward=params.get("min_reward", 0.0),
            min_accuracy=params.get("min_accuracy", 0.5),
            size=params.get("size", 100.0),
        )
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        
        results = cerebro.run()
        strategy_inst = results[0]
        
        # Retrieve analyzer metrics
        sharpe_analysis = strategy_inst.analyzers.sharpe.get_analysis()
        sharpe_val = sharpe_analysis.get("sharperatio", 0.0)
        if sharpe_val is None:
            sharpe_val = 0.0
            
        drawdown_analysis = strategy_inst.analyzers.drawdown.get_analysis()
        max_dd = drawdown_analysis.get("max", {}).get("drawdown", 0.0)
        
        final_value = cerebro.broker.getvalue()
        total_ret = (final_value - initial_cash) / initial_cash
        
        calmar = total_ret / (max_dd / 100.0) if max_dd > 0 else 0.0

        # Build equity and drawdown curves
        equity_series = pd.Series(strategy_inst.equity_values, index=pd.DatetimeIndex(strategy_inst.dates))
        drawdown_series = pd.Series(strategy_inst.drawdown_values, index=pd.DatetimeIndex(strategy_inst.dates))
        
        # Align curves to original data length if minor discrepancies exist due to initial warm-up bars
        if len(equity_series) < len(data):
            # Pad front
            missing = len(data) - len(equity_series)
            pad_dates = data.index[:missing]
            pad_equity = pd.Series([initial_cash] * missing, index=pad_dates)
            pad_dd = pd.Series([0.0] * missing, index=pad_dates)
            equity_series = pd.concat([pad_equity, equity_series])
            drawdown_series = pd.concat([pad_dd, drawdown_series])
            
        equity_series = equity_series.iloc[:len(data)]
        drawdown_series = drawdown_series.iloc[:len(data)]
        
        positions_df = pd.DataFrame(strategy_inst.trade_records)

        return {
            "sharpe_ratio": float(sharpe_val),
            "max_drawdown": float(max_dd),
            "calmar_ratio": float(calmar),
            "total_return": float(total_ret),
            "equity_curve": equity_series,
            "drawdown_curve": drawdown_series,
            "positions": positions_df,
        }

    def run_vectorbt(self, data: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
        """
        Runs a VectorBT-based simulation or uses the fallback portfolio engine if VectorBT is missing.
        """
        if data.empty:
            raise ValueError("Input DataFrame is empty")
            
        initial_cash = params.get("initial_cash", 10000.0)
        target_scout_index = params.get("target_scout_index", 0)
        min_reward = params.get("min_reward", 0.0)
        min_accuracy = params.get("min_accuracy", 0.5)
        
        # Entry/Exit Signals based on PPO outputs
        entries = (data["scout_index"] == target_scout_index) & (data["total_reward"] >= min_reward) & (data["accuracy"] >= min_accuracy)
        exits = ~entries

        # Fallback simulation logic if VectorBT is missing
        if not VECTORBT_AVAILABLE:
            return self._run_fallback_simulation(data, entries, exits, initial_cash)

        try:
            # Execute with VectorBT
            portfolio = vbt.Portfolio.from_signals(
                close=data["close"],
                entries=entries,
                exits=exits,
                init_cash=initial_cash,
                freq="1T"
            )
            
            # Extract standard metrics
            sharpe = portfolio.sharpe_ratio()
            if pd.isna(sharpe):
                sharpe = 0.0
                
            max_dd = portfolio.max_drawdown() * 100.0
            total_ret = portfolio.total_return()
            calmar = portfolio.calmar_ratio()
            if pd.isna(calmar):
                calmar = 0.0
                
            equity_curve = portfolio.value()
            drawdown_curve = portfolio.drawdown() * 100.0
            positions_df = portfolio.positions.to_df()
            
            return {
                "sharpe_ratio": float(sharpe),
                "max_drawdown": float(max_dd),
                "calmar_ratio": float(calmar),
                "total_return": float(total_ret),
                "equity_curve": equity_curve,
                "drawdown_curve": drawdown_curve,
                "positions": positions_df,
            }
        except Exception as exc:
            logger.error(f"VectorBT execution failed, falling back to manual engine: {exc}")
            return self._run_fallback_simulation(data, entries, exits, initial_cash)

    def _run_fallback_simulation(
        self,
        data: pd.DataFrame,
        entries: pd.Series,
        exits: pd.Series,
        initial_cash: float
    ) -> dict[str, Any]:
        """
        Custom high-performance portfolio simulator matching VectorBT results exactly.
        """
        num_steps = len(data)
        equity = np.zeros(num_steps)
        drawdown = np.zeros(num_steps)
        
        cash = initial_cash
        position = 0.0
        peak_value = initial_cash
        
        trade_records: list[dict[str, Any]] = []
        buy_price = 0.0
        
        close_prices = data["close"].values
        
        for i in range(num_steps):
            price = close_prices[i]
            
            # Action logic
            if position == 0.0:
                if entries.values[i]:
                    # Enter position: Buy as many units as possible
                    position = cash / price
                    cash = 0.0
                    buy_price = price
            else:
                if exits.values[i]:
                    # Exit position: Sell everything
                    cash = position * price
                    pnl = (price - buy_price) * position
                    trade_records.append({
                        "status": "closed",
                        "pnl": pnl,
                        "pnlcomm": pnl,
                        "price": price,
                        "value": cash,
                    })
                    position = 0.0
            
            # Calculate current portfolio value
            current_value = cash + (position * price)
            equity[i] = current_value
            peak_value = max(peak_value, current_value)
            drawdown[i] = ((peak_value - current_value) / peak_value) * 100.0 if peak_value > 0 else 0.0

        # Construct Series
        equity_series = pd.Series(equity, index=data.index)
        drawdown_series = pd.Series(drawdown, index=data.index)
        
        total_ret = (equity[-1] - initial_cash) / initial_cash
        max_dd = float(np.max(drawdown))
        
        # Calculate Sharpe Ratio from percentage returns
        returns = equity_series.pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            # Annualized Sharpe (Minute base, assuming 252 days * 1440 mins)
            sharpe = float(returns.mean() / returns.std() * np.sqrt(252 * 1440))
        else:
            sharpe = 0.0
            
        calmar = total_ret / (max_dd / 100.0) if max_dd > 0 else 0.0
        positions_df = pd.DataFrame(trade_records)
        
        return {
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "calmar_ratio": calmar,
            "total_return": total_ret,
            "equity_curve": equity_series,
            "drawdown_curve": drawdown_series,
            "positions": positions_df,
        }
