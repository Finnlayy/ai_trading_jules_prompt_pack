from __future__ import annotations

import itertools
from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import minimize, differential_evolution


def scipy_optimize(
    runner: Any,
    data: pd.DataFrame,
    initial_params: dict[str, Any],
    weights: dict[str, float],
    method: str = "differential_evolution",
    maxiter: int = 10,
) -> dict[str, Any]:
    """
    Optimizes PPO policy parameters (scout thresholds, reward weights)
    using scipy.optimize global or local search methods.
    
    Objective: maximize a weighted score combining Sharpe Ratio, Max Drawdown, and Calmar Ratio.
    """
    # Parameters to optimize:
    # x[0]: min_reward (bounds: [0.0, 1.0])
    # x[1]: min_accuracy (bounds: [0.4, 0.95])
    # x[2:10]: 8 reward weights (accuracy, calibration, curriculum, ab_lift, spec, div, echo, divg)
    
    # Starting values
    x0 = [
        initial_params.get("min_reward", 0.0),
        initial_params.get("min_accuracy", 0.5),
        1.20,  # accuracy weight
        0.90,  # calibration weight
        0.70,  # curriculum progress weight
        0.60,  # ab_lift weight
        0.45,  # specialization weight
        0.25,  # diversity weight
        -0.80, # echo penalty weight
        -0.60, # divergence penalty weight
    ]

    bounds = [
        (0.0, 1.0),      # min_reward
        (0.4, 0.95),     # min_accuracy
        (0.0, 2.5),      # accuracy weight
        (0.0, 2.0),      # calibration weight
        (0.0, 2.0),      # curriculum progress weight
        (0.0, 2.0),      # ab_lift weight
        (0.0, 1.5),      # specialization weight
        (0.0, 1.0),      # diversity weight
        (-2.0, 0.0),     # echo penalty weight
        (-1.5, 0.0),     # divergence penalty weight
    ]

    def objective(x: np.ndarray) -> float:
        # Clone the dataset to modify rewards without side effects
        working_data = data.copy()
        
        # Recalculate total_reward using optimized weights if individual delta columns exist
        # If they don't, we simulate using standard formulas or use total_reward scaled
        has_deltas = all(col in working_data.columns for col in ["accuracy_delta", "calibration_delta", "curriculum_delta"])
        if has_deltas:
            # from reward.py formula
            total = (
                x[2] * working_data.get("accuracy_delta", 0.0) +
                x[3] * working_data.get("calibration_delta", 0.0) +
                x[4] * working_data.get("curriculum_delta", 0.0) +
                x[5] * working_data.get("ab_lift_delta", 0.0) +
                x[6] * working_data.get("specialization_delta", 0.0) +
                x[7] * working_data.get("diversity_health", 0.0) +
                x[8] * working_data.get("echo_penalty", 0.0) +
                x[9] * working_data.get("divergence_penalty", 0.0)
            )
            working_data["total_reward"] = np.clip(total, -3.0, 3.0)
        else:
            # Default scaling factor based on reward weight adjustments
            scale = (x[2] + x[3] + x[4] + x[5] + x[6] + x[7]) / 4.10
            working_data["total_reward"] = working_data["total_reward"] * scale

        # Assemble run parameters
        run_params = {
            "target_scout_index": initial_params.get("target_scout_index", 0),
            "min_reward": float(x[0]),
            "min_accuracy": float(x[1]),
            "initial_cash": initial_params.get("initial_cash", 10000.0),
        }

        # Run vectorbt (or fallback) since it's faster for optimization iterations
        try:
            res = runner.run_vectorbt(working_data, run_params)
            sharpe = res.get("sharpe_ratio", 0.0)
            drawdown = res.get("max_drawdown", 0.0)
            calmar = res.get("calmar_ratio", 0.0)
        except Exception:
            return 9999.0  # Penalty for failed simulation

        # Objective combination
        score = (
            weights.get("sharpe", 1.0) * sharpe -
            weights.get("drawdown", 1.0) * drawdown +
            weights.get("calmar", 1.0) * calmar
        )
        return -score  # Minimize negative score to maximize actual score

    iterations = 0

    def callback(*args, **kwargs):
        nonlocal iterations
        iterations += 1

    if method == "differential_evolution":
        res_opt = differential_evolution(
            objective,
            bounds=bounds,
            maxiter=maxiter,
            callback=callback
        )
        opt_x = res_opt.x
        success = res_opt.success
    else:
        res_opt = minimize(
            objective,
            x0=np.array(x0),
            bounds=bounds,
            method="L-BFGS-B",
            options={"maxiter": maxiter},
            callback=callback
        )
        opt_x = res_opt.x
        success = res_opt.success

    # Calculate optimal results using best parameters
    best_reward = float(opt_x[0])
    best_accuracy = float(opt_x[1])
    
    final_params = initial_params.copy()
    final_params["min_reward"] = best_reward
    final_params["min_accuracy"] = best_accuracy
    final_params["reward_weights"] = {
        "accuracy": float(opt_x[2]),
        "calibration": float(opt_x[3]),
        "curriculum": float(opt_x[4]),
        "ab_lift": float(opt_x[5]),
        "specialization": float(opt_x[6]),
        "diversity": float(opt_x[7]),
        "echo_penalty": float(opt_x[8]),
        "divergence_penalty": float(opt_x[9]),
    }

    # Run final simulation to return actual metrics
    final_res = runner.run_vectorbt(data, final_params)

    return {
        "optimal_params": final_params,
        "sharpe_ratio": final_res["sharpe_ratio"],
        "max_drawdown": final_res["max_drawdown"],
        "calmar_ratio": final_res["calmar_ratio"],
        "total_return": final_res["total_return"],
        "iterations": iterations,
        "success": success,
    }


def vectorbt_grid_search(data: pd.DataFrame, param_grid: dict[str, list[Any]]) -> pd.DataFrame:
    """
    Performs grid search parameter sweeps across ranges of thresholds.
    """
    from app.services.academy_policy.backtesting.backtest_runner import BacktestRunner
    
    runner = BacktestRunner()
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    
    results = []
    
    # Generate combinations
    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        
        # Run backtest
        try:
            res = runner.run_vectorbt(data, params)
            row = params.copy()
            row["sharpe_ratio"] = res["sharpe_ratio"]
            row["max_drawdown"] = res["max_drawdown"]
            row["calmar_ratio"] = res["calmar_ratio"]
            row["total_return"] = res["total_return"]
            results.append(row)
        except Exception:
            pass
            
    return pd.DataFrame(results)
