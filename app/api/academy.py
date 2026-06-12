import asyncio
import json
import math
import re
import uuid
from pathlib import Path as FsPath
from typing import Any, Dict, List
from collections import deque

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.services.agent_registry import agent_registry

router = APIRouter(prefix="/academy", tags=["Academy"])
REPORTS_DIR = FsPath("data/academy_policy/backtesting/reports")


class AgentDeployRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    archetype: str = Field(default="Analyst", min_length=1, max_length=64)
    personality_vector: Dict[str, float] = Field(default_factory=dict)
    specialization_symbols: List[str] = Field(default_factory=list)

@router.get("/agents/registry")
def get_agents_registry():
    agents = agent_registry.get_all_identities()
    return {"agents": [a.model_dump() for a in agents]}


@router.post("/agents/deploy")
def deploy_agent(req: AgentDeployRequest | None = None):
    req = req or AgentDeployRequest()
    try:
        agent = agent_registry.deploy_identity(
            name=req.name,
            archetype=req.archetype,
            personality_vector=req.personality_vector,
            specialization_symbols=req.specialization_symbols,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return {"status": "created", "agent": agent.model_dump()}

@router.get("/agents/{scout_id}/career")
def get_agent_career(scout_id: str):
    # Using scout_id as scout_name for now since that's what's tracked mostly
    entries = agent_registry.get_career_log(scout_id)
    return {"career": [e.model_dump() for e in entries]}

@router.get("/agents/careers/recent")
def get_recent_agent_careers(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None),
):
    entries = agent_registry.get_recent_career_events(limit=limit, event_type=event_type)
    return {"career": [e.model_dump() for e in entries], "count": len(entries)}

@router.get("/agents/leaderboard")
def get_leaderboard():
    agents = agent_registry.get_all_identities()

    leaderboard = []
    for agent in agents:
        top_badge = None
        if agent.badges:
            # Simple heuristic: last earned badge is often highest, or just pick one
            top_badge = agent.badges[-1].model_dump()

        leaderboard.append({
            "scout_name": agent.name,
            "archetype": agent.archetype,
            "accuracy": agent.accuracy,
            "experience": agent.total_calls,
            "specialization_score": 0.0, # Will be aggregated later if needed from ConfidenceRegistry
            "top_badge": top_badge,
            "badges": [b.model_dump() for b in agent.badges]
        })

    leaderboard.sort(key=lambda x: (x["accuracy"], x["experience"]), reverse=True)
    return {"leaderboard": leaderboard}

from app.services.training_drills import training_drills
from app.services.prompt_evolution import prompt_evolution
from app.services.ab_testing import ab_testing
from app.services.academy_curriculum import academy_curriculum
from app.schemas.academy import (
    AcademyBacktestingGridSearchRequest,
    AcademyBacktestingOptimizeRequest,
    AcademyBacktestingReportRequest,
    AcademyBacktestingRunRequest,
    AcademyPolicyPreviewRequest,
    SyntheticDrill,
)
from app.services.academy_policy import academy_policy_service
from app.services.academy_policy.logging import ACTION_LOG_FILE

@router.get("/drills/available")
def get_available_drills(scout_name: str, count: int = 5):
    drills = training_drills.generate_drills(scout_name, count)
    return {"drills": [d.model_dump() for d in drills]}

@router.post("/drill/evaluate")
async def evaluate_drill(drill: SyntheticDrill, scout_decision: str, confidence: float = 0.8):
    result = await training_drills.evaluate_drill(drill, scout_decision, confidence)
    academy_curriculum.record_drill_result(drill.scout_target, "Beginner", result.is_correct, result.confidence)
    return result.model_dump()

@router.get("/ab-tests")
def get_ab_tests():
    tests = ab_testing.get_all()
    return {"ab_tests": [t.model_dump() for t in tests]}

@router.get("/curriculum/{scout_name}")
def get_curriculum(scout_name: str):
    progress = academy_curriculum.get_all_for_scout(scout_name)
    return {"curriculum": [p.model_dump() for p in progress]}

from app.services.training_loop import training_loop

@router.get("/status")
def get_academy_status():
    return training_loop.get_status()


@router.get("/policy/status")
def get_academy_policy_status():
    return academy_policy_service.get_status().model_dump()


@router.post("/policy/preview")
def preview_academy_policy(req: AcademyPolicyPreviewRequest | None = None):
    return academy_policy_service.preview(req or AcademyPolicyPreviewRequest())


@router.get("/policy/actions/recent")
def get_recent_policy_actions(limit: int = Query(default=50, ge=1, le=500)):
    if not ACTION_LOG_FILE.exists():
        return {"actions": [], "count": 0}

    actions = []
    try:
        line_deque = deque(maxlen=limit)
        with ACTION_LOG_FILE.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    line_deque.append(line)
        for line in reversed(line_deque):
            actions.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read academy policy actions: {exc}")

    return {"actions": actions, "count": len(actions)}


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _clean_json_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_json_value(item) for item in value]
    return value


def _records_to_dataframe(records: list[Any]) -> pd.DataFrame:
    from app.services.academy_policy.backtesting.data_adapter import dataframe_to_vectorbt_format

    rows: list[dict[str, Any]] = []
    timestamps: list[str | None] = []
    for record in records:
        row = record.model_dump(exclude_none=True)
        timestamps.append(row.pop("timestamp", None))
        rows.append(row)

    if any(timestamp is not None for timestamp in timestamps):
        if any(timestamp is None for timestamp in timestamps):
            raise ValueError("All records must include timestamp when any record includes timestamp")
        index = pd.to_datetime(timestamps, utc=True, errors="coerce")
        if pd.isna(index).any():
            raise ValueError("Invalid timestamp in records")
        index = pd.DatetimeIndex(index).tz_convert(None)
    else:
        index = pd.date_range("2026-06-01 12:00:00", periods=len(rows), freq="1min")

    data = pd.DataFrame(rows, index=index)
    if "close" not in data.columns or data["close"].isna().any():
        raise ValueError("Each record must include a valid close price")

    for column in data.columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = dataframe_to_vectorbt_format(data)
    if (data["close"] <= 0).any():
        raise ValueError("Close prices must be greater than zero")
    return data


def _series_points(series: pd.Series) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": index.isoformat() if hasattr(index, "isoformat") else str(index),
            "value": _clean_json_value(float(value)),
        }
        for index, value in series.items()
    ]


def _frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return [
        {str(key): _clean_json_value(value) for key, value in row.items()}
        for row in frame.reset_index(drop=True).to_dict(orient="records")
    ]


def _compact_backtest_result(backend: str, result: dict[str, Any]) -> dict[str, Any]:
    metrics = {
        "sharpe_ratio": _clean_json_value(float(result.get("sharpe_ratio", 0.0))),
        "max_drawdown": _clean_json_value(float(result.get("max_drawdown", 0.0))),
        "calmar_ratio": _clean_json_value(float(result.get("calmar_ratio", 0.0))),
        "total_return": _clean_json_value(float(result.get("total_return", 0.0))),
    }
    positions = result.get("positions")
    position_records = _frame_records(positions) if isinstance(positions, pd.DataFrame) else []
    return {
        "status": "success",
        "backend": backend,
        "metrics": metrics,
        "equity_curve": _series_points(result["equity_curve"]),
        "drawdown_curve": _series_points(result["drawdown_curve"]),
        "positions": position_records,
        "position_count": len(position_records),
    }


def _run_backend(backend: str, data: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    from app.services.academy_policy.backtesting.backtest_runner import BacktestRunner

    runner = BacktestRunner()
    if backend == "backtrader":
        return runner.run_backtrader(data, params)
    return runner.run_vectorbt(data, params)


def _run_backtesting_request(req: AcademyBacktestingRunRequest) -> dict[str, Any]:
    data = _records_to_dataframe(req.records)
    result = _run_backend(req.backend, data, req.params)
    return _compact_backtest_result(req.backend, result)


def _optimize_backtesting_request(req: AcademyBacktestingOptimizeRequest) -> dict[str, Any]:
    from app.services.academy_policy.backtesting.backtest_runner import BacktestRunner
    from app.services.academy_policy.backtesting.optimizer import scipy_optimize

    data = _records_to_dataframe(req.records)
    result = scipy_optimize(
        runner=BacktestRunner(),
        data=data,
        initial_params=req.initial_params,
        weights=req.weights,
        method=req.method,
        maxiter=req.maxiter,
    )
    return {
        "status": "success",
        "method": req.method,
        "success": bool(result.get("success")),
        "iterations": int(result.get("iterations", 0)),
        "optimal_params": _clean_json_value(result.get("optimal_params", {})),
        "metrics": {
            "sharpe_ratio": _clean_json_value(float(result.get("sharpe_ratio", 0.0))),
            "max_drawdown": _clean_json_value(float(result.get("max_drawdown", 0.0))),
            "calmar_ratio": _clean_json_value(float(result.get("calmar_ratio", 0.0))),
            "total_return": _clean_json_value(float(result.get("total_return", 0.0))),
        },
    }


def _grid_search_backtesting_request(req: AcademyBacktestingGridSearchRequest) -> dict[str, Any]:
    from app.services.academy_policy.backtesting.optimizer import vectorbt_grid_search

    data = _records_to_dataframe(req.records)
    results = vectorbt_grid_search(data, req.param_grid)
    return {
        "status": "success",
        "row_count": len(results),
        "results": _frame_records(results),
    }


def _report_filename(kind: str) -> str:
    return f"{kind}_{uuid.uuid4().hex}.png"


def _chart_entry(kind: str, filename: str) -> dict[str, str]:
    return {
        "kind": kind,
        "path": f"/academy/policy/backtesting/reports/{filename}",
    }


def _build_report_charts(
    data: pd.DataFrame,
    result: dict[str, Any],
    params: dict[str, Any],
) -> list[dict[str, str]]:
    from app.services.academy_policy.backtesting.visualizer import (
        plot_drawdown,
        plot_equity_curve,
        plot_kpi_time_series,
        plot_reward_history,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    charts: list[dict[str, str]] = []

    initial_cash = float(params.get("initial_cash", 10000.0))
    benchmark = data["close"] / data["close"].iloc[0] * initial_cash

    equity_name = _report_filename("equity")
    plot_equity_curve(result["equity_curve"], benchmark=benchmark, save_path=str(REPORTS_DIR / equity_name))
    charts.append(_chart_entry("equity_curve", equity_name))

    drawdown_name = _report_filename("drawdown")
    plot_drawdown(result["drawdown_curve"], save_path=str(REPORTS_DIR / drawdown_name))
    charts.append(_chart_entry("drawdown", drawdown_name))

    kpi_columns = [col for col in ("accuracy", "calibration", "ab_lift") if col in data.columns]
    if kpi_columns:
        kpi_name = _report_filename("kpi")
        scout_activations = [
            (timestamp, int(scout_idx))
            for timestamp, scout_idx in data["scout_index"].items()
        ] if "scout_index" in data.columns else None
        plot_kpi_time_series(data[kpi_columns], scout_activations=scout_activations, save_path=str(REPORTS_DIR / kpi_name))
        charts.append(_chart_entry("kpi_time_series", kpi_name))

    if "total_reward" in data.columns:
        reward_name = _report_filename("reward")
        plot_reward_history(data["total_reward"], save_path=str(REPORTS_DIR / reward_name))
        charts.append(_chart_entry("reward_history", reward_name))

    return charts


def _report_backtesting_request(req: AcademyBacktestingReportRequest) -> dict[str, Any]:
    data = _records_to_dataframe(req.records)
    result = _run_backend(req.backend, data, req.params)
    response = _compact_backtest_result(req.backend, result)
    response["charts"] = _build_report_charts(data, result, req.params) if req.include_charts else []
    return response


@router.post("/policy/backtesting/run")
async def run_academy_policy_backtest(req: AcademyBacktestingRunRequest):
    try:
        return await asyncio.to_thread(_run_backtesting_request, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Academy policy backtest failed: {exc}")


@router.post("/policy/backtesting/optimize")
async def optimize_academy_policy_backtest(req: AcademyBacktestingOptimizeRequest):
    try:
        return await asyncio.to_thread(_optimize_backtesting_request, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Academy policy optimization failed: {exc}")


@router.post("/policy/backtesting/grid-search")
async def grid_search_academy_policy_backtest(req: AcademyBacktestingGridSearchRequest):
    try:
        return await asyncio.to_thread(_grid_search_backtesting_request, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Academy policy grid search failed: {exc}")


@router.post("/policy/backtesting/report")
async def report_academy_policy_backtest(req: AcademyBacktestingReportRequest):
    try:
        return await asyncio.to_thread(_report_backtesting_request, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Academy policy report failed: {exc}")


@router.get("/policy/backtesting/reports/{filename}")
def get_academy_policy_backtesting_report(filename: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", filename):
        raise HTTPException(status_code=404, detail="Report artifact not found")

    reports_root = REPORTS_DIR.resolve()
    report_path = (REPORTS_DIR / filename).resolve()
    try:
        report_path.relative_to(reports_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report artifact not found")

    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report artifact not found")
    return FileResponse(report_path, media_type="image/png")

@router.post("/train/start")
async def start_training():
    result = await training_loop.start()
    return {"status": "started" if result.get("started") else "not_started", **result}


@router.post("/train/stop")
async def stop_training():
    await training_loop.stop()
    return {"status": "stopped"}

@router.post("/drill/start")
async def trigger_manual_drill():
    await training_loop.trigger_manual_cycle()
    return {"status": "drill_cycle_completed"}


@router.get("/policy/onnx/details")
def get_onnx_policy_details():
    """Fetch compiled ONNX policy models, version information, latency, and input mapping."""
    import time
    from pathlib import Path
    from app.core.config import ACADEMY_POLICY_MODEL_DIR
    from app.services.academy_policy.state import OBSERVATION_SIZE
    
    model_dir = Path(ACADEMY_POLICY_MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    onnx_files = list(model_dir.glob("*.onnx"))
    
    models = []
    active_latency = None
    
    # Read active model manifest if present
    manifest_path = model_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    for f in onnx_files:
        is_active = (f.name == "policy.onnx")
        latency_ms = None
        inputs_list = []
        outputs_list = []
        load_error = None
        stat = f.stat()
        
        try:
            import onnxruntime as ort
            import numpy as np
            
            # Setup session
            sess = ort.InferenceSession(str(f), providers=["CPUExecutionProvider"])
            
            inputs = sess.get_inputs()
            for inp in inputs:
                inputs_list.append({
                    "name": inp.name,
                    "shape": inp.shape,
                    "type": inp.type
                })
                
            outputs = sess.get_outputs()
            for out in outputs:
                outputs_list.append({
                    "name": out.name,
                    "shape": out.shape,
                    "type": out.type
                })
            
            if inputs:
                input_name = inputs[0].name
                input_shape = inputs[0].shape
                
                # Resolve dummy observation shape
                dummy_shape = input_shape or [1, OBSERVATION_SIZE]
                # Handle dynamic dimensions (e.g. batch size indicated by strings or None)
                dummy_shape = [x if isinstance(x, int) and x > 0 else 1 for x in dummy_shape]
                
                dummy_obs = np.zeros(dummy_shape, dtype=np.float32)
                
                # Warm up
                sess.run(None, {input_name: dummy_obs})
                
                # Measure latency over 10 iterations
                t0 = time.perf_counter()
                for _ in range(10):
                    sess.run(None, {input_name: dummy_obs})
                t1 = time.perf_counter()
                latency_ms = round(((t1 - t0) / 10) * 1000, 3)
                
                if is_active:
                    active_latency = latency_ms
        except Exception as exc:
            load_error = str(exc)
            
        models.append({
            "filename": f.name,
            "path": str(f),
            "is_active": is_active,
            "latency_ms": latency_ms,
            "inputs": inputs_list,
            "outputs": outputs_list,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "load_error": load_error,
            "model_id": manifest.get("model_id") if is_active else f.stem,
        })
        
    return {
        "status": "ok",
        "models": models,
        "active_latency_ms": active_latency,
        "feature_version": manifest.get("feature_version"),
        "observation_size": OBSERVATION_SIZE,
    }


@router.post("/policy/onnx/open-folder")
def open_onnx_folder():
    """Open the directory containing compiled ONNX policy models in the system file explorer."""
    import os
    import subprocess
    from pathlib import Path
    from app.core.config import ACADEMY_POLICY_MODEL_DIR
    
    model_dir = Path(ACADEMY_POLICY_MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    abs_path = model_dir.resolve()
    
    try:
        if os.name == 'nt':
            os.startfile(abs_path)
        elif os.name == 'posix':
            subprocess.run(['xdg-open', str(abs_path)], check=True)
        else:
            # Fallback for MacOS
            subprocess.run(['open', str(abs_path)], check=True)
        return {"status": "success", "path": str(abs_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {e}")

