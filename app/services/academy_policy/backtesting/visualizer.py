from __future__ import annotations

from typing import Any
import os
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

# Set standard premium styling
sns.set_theme(style="darkgrid")
plt.rcParams.update({
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.titlesize": 14,
    "grid.color": "#e0e0e0",
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
})

# Harmonious Color Palette
PRIMARY_COLOR = "#4f46e5"  # Indigo
SECONDARY_COLOR = "#0ea5e9" # Sky
ACCENT_COLOR = "#f43f5e"    # Rose
BENCHMARK_COLOR = "#94a3b8" # Slate
DIVERGENT_PALETTE = "coolwarm"


def _handle_save_and_close(
    fig: plt.Figure,
    save_path: str | None = None
) -> plt.Figure:
    """
    Helper function to save the figure if save_path is provided and close it.
    """
    if save_path:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight")
        plt.close(fig)
    return fig


def plot_equity_curve(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
    save_path: str | None = None,
    figsize: tuple[int, int] = (10, 5),
    dpi: int = 100
) -> plt.Figure:
    """
    Plots the portfolio equity curve over time, optionally overlaying a benchmark.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    ax.plot(equity.index, equity.values, label="PPO Policy Strategy", color=PRIMARY_COLOR, linewidth=2)
    
    if benchmark is not None:
        ax.plot(benchmark.index, benchmark.values, label="Benchmark (Hold)", color=BENCHMARK_COLOR, linestyle="--", linewidth=1.5)
        
    ax.set_title("Equity Curve vs Benchmark")
    ax.set_xlabel("Timeline")
    ax.set_ylabel("Portfolio Value (USDT)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    
    return _handle_save_and_close(fig, save_path)


def plot_drawdown(
    drawdown: pd.Series,
    save_path: str | None = None,
    figsize: tuple[int, int] = (10, 4),
    dpi: int = 100
) -> plt.Figure:
    """
    Plots the percentage drawdown curve over time.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    ax.fill_between(drawdown.index, drawdown.values, 0, color=ACCENT_COLOR, alpha=0.3, label="Drawdown %")
    ax.plot(drawdown.index, drawdown.values, color=ACCENT_COLOR, linewidth=1)
    
    ax.set_title("Portfolio Drawdown %")
    ax.set_xlabel("Timeline")
    ax.set_ylabel("Drawdown Percentage")
    ax.legend(loc="lower left")
    fig.tight_layout()
    
    return _handle_save_and_close(fig, save_path)


def plot_kpi_time_series(
    kpi_df: pd.DataFrame,
    scout_activations: list[tuple[pd.Timestamp, int]] | None = None,
    save_path: str | None = None,
    figsize: tuple[int, int] = (12, 6),
    dpi: int = 100
) -> plt.Figure:
    """
    Plots timelines for scout KPIs (Accuracy, Calibration, A/B-Lift)
    and overlays vertical lines for scout activation decisions.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    colors = [PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR]
    for col, color in zip(kpi_df.columns, colors):
        ax.plot(kpi_df.index, kpi_df[col], label=col.capitalize(), color=color, linewidth=1.5)
        
    # Overlay scout activations as vertical lines
    if scout_activations:
        for timestamp, scout_idx in scout_activations:
            ax.axvline(timestamp, color="#4b5563", linestyle=":", alpha=0.7, linewidth=1.2)
            # Add text label for the activated scout index
            y_lim = ax.get_ylim()
            ax.text(
                timestamp,
                y_lim[1] - (y_lim[1] - y_lim[0]) * 0.05,
                f"S{scout_idx}",
                rotation=90,
                verticalalignment="top",
                fontsize=8,
                color="#374151"
            )
            
    ax.set_title("Scout KPI Timelines & Activation Decisions")
    ax.set_xlabel("Timeline")
    ax.set_ylabel("KPI Value")
    ax.legend(loc="upper left")
    fig.tight_layout()
    
    return _handle_save_and_close(fig, save_path)


def plot_reward_history(
    rewards: pd.Series,
    save_path: str | None = None,
    figsize: tuple[int, int] = (10, 4),
    dpi: int = 100
) -> plt.Figure:
    """
    Plots the scalar PPO rewards over training steps or time steps.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Calculate rolling mean to smooth out rewards
    rolling_mean = rewards.rolling(window=max(1, len(rewards)//10)).mean()
    
    ax.plot(rewards.index, rewards.values, color=SECONDARY_COLOR, alpha=0.4, label="Raw Reward")
    ax.plot(rewards.index, rolling_mean.values, color=PRIMARY_COLOR, linewidth=2, label="Rolling Avg Reward")
    
    ax.set_title("PPO Policy Reward History")
    ax.set_xlabel("Steps")
    ax.set_ylabel("Reward Value")
    ax.legend(loc="upper left")
    fig.tight_layout()
    
    return _handle_save_and_close(fig, save_path)


def plot_parameter_heatmap(
    results_df: pd.DataFrame,
    x_col: str,
    y_col: str,
    metric_col: str,
    save_path: str | None = None,
    figsize: tuple[int, int] = (8, 6),
    dpi: int = 100
) -> plt.Figure:
    """
    Generates a heatmap representation of parameter sweep results (e.g. min_reward vs min_accuracy).
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Pivot dataframe to construct grid
    pivot_table = results_df.pivot(index=y_col, columns=x_col, values=metric_col)
    
    sns.heatmap(
        pivot_table,
        annot=True,
        fmt=".3f",
        cmap=DIVERGENT_PALETTE,
        ax=ax,
        cbar_kws={"label": metric_col.replace("_", " ").capitalize()}
    )
    
    ax.set_title(f"Parameter Sweep Grid: {metric_col.replace('_', ' ').capitalize()}")
    ax.set_xlabel(x_col.replace("_", " ").capitalize())
    ax.set_ylabel(y_col.replace("_", " ").capitalize())
    fig.tight_layout()
    
    return _handle_save_and_close(fig, save_path)


def plot_reward_distribution(
    rewards_df: pd.DataFrame,
    save_path: str | None = None,
    figsize: tuple[int, int] = (10, 5),
    dpi: int = 100
) -> plt.Figure:
    """
    Generates distribution plots (KDE + Histogram overlay) for PPO rewards per active scout.
    
    Expects rewards_df to contain columns: 'scout_name' and 'reward'.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Render distributions per scout (showing top 4 scouts for legibility if needed, or all)
    scouts = rewards_df["scout_name"].unique()
    for scout in scouts[:5]:  # Limit to 5 scouts to avoid visual clutter
        scout_data = rewards_df[rewards_df["scout_name"] == scout]["reward"]
        sns.histplot(
            scout_data,
            kde=True,
            stat="density",
            alpha=0.3,
            label=scout.capitalize(),
            ax=ax,
            element="step"
        )
        
    ax.set_title("Reward Value Distributions per Active Scout")
    ax.set_xlabel("Reward Value")
    ax.set_ylabel("Density")
    ax.legend(loc="upper right")
    fig.tight_layout()
    
    return _handle_save_and_close(fig, save_path)


def plot_kpi_correlation(
    kpis_df: pd.DataFrame,
    save_path: str | None = None,
    figsize: tuple[int, int] = (12, 10),
    dpi: int = 100
) -> plt.Figure:
    """
    Plots a 16x16 correlation matrix of scout KPIs to analyze echo chamber behavior.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    corr = kpis_df.corr()
    
    # Generate mask for upper triangle
    mask = np.triu(np.ones_like(corr, dtype=bool))
    
    sns.heatmap(
        corr,
        mask=mask,
        cmap=DIVERGENT_PALETTE,
        vmax=1.0,
        vmin=-1.0,
        center=0,
        square=True,
        linewidths=.5,
        cbar_kws={"shrink": .7, "label": "Correlation Coefficient"},
        ax=ax,
        annot=False
    )
    
    ax.set_title("16x16 Scout KPI Correlation Matrix (Regime Divergence)")
    fig.tight_layout()
    
    return _handle_save_and_close(fig, save_path)


def fig_to_base64(fig: plt.Figure) -> str:
    """
    Converts a matplotlib/seaborn figure into a base64-encoded PNG image string.
    """
    import io
    import base64
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"

