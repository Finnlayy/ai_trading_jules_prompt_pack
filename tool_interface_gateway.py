#!/usr/bin/env python3
"""Allowlisted JSON dispatcher between Gems and the FastAPI trading backend."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import importlib
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

import app.core.config as config
from risk_gate_validator import validate_risk_gates


class ToolGatewayRequest(BaseModel):
    """Validated Gem tool request."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ai_review: dict[str, Any] | None = None
    risk_context: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


TOOL_ALIASES = {
    "risk.validate": "risk.validate",
    "risk_gate.validate": "risk.validate",
    "risk_gate_validator.validate": "risk.validate",
    "signal.preflight": "risk.validate",
    "m8.preflight": "risk.validate",
    "backend.health": "backend.health",
    "backend.m8": "backend.m8",
    "m8.submit": "backend.m8",
    "signal.submit": "backend.m8",
    "optimizer.ga_hype": "optimizer.ga_hype",
    "ga_forward_optimizer": "optimizer.ga_hype",
    "optimizer.crossalgo_hype": "optimizer.crossalgo_hype",
    "optimizer.generate_ga_pines": "optimizer.generate_ga_pines",
    "quality.check": "quality.check",
    "trade.report": "trade.report",
    "trade_analyzer.report": "trade.report",
}


EXPENSIVE_MODULE_TOOLS = {
    "optimizer.ga_hype": ("app.scripts.ga_optimize_hype", "main"),
    "optimizer.crossalgo_hype": ("app.scripts.ga_crossalgo_hype", "main"),
    "optimizer.generate_ga_pines": ("app.scripts.generate_ga_pines", "main"),
}


def _json_error(request_id: str | None, code: str, detail: Any, status: str = "error") -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "request_id": request_id,
        "error_code": code,
        "detail": detail,
        "result": None,
    }


def _json_success(request_id: str, result: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "success",
        "request_id": request_id,
        "error_code": None,
        "detail": None,
        "result": result,
    }


def _normalize_tool(name: str) -> str | None:
    return TOOL_ALIASES.get(name.strip())


def _backend_base_url(options: dict[str, Any]) -> str:
    return str(
        options.get("backend_url")
        or os.getenv("GEM_GATEWAY_BACKEND_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _is_local_backend(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _compact_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign_body_if_configured(body: bytes, headers: dict[str, str]) -> None:
    secret = config.WEBHOOK_SECRET or os.getenv("WEBHOOK_SECRET", "")
    if not secret:
        return
    headers["x-m8-signature"] = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()


def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    body = _compact_body(payload) if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        _sign_body_if_configured(body, headers)

    req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            try:
                parsed: Any = json.loads(text)
            except json.JSONDecodeError:
                parsed = text
            return {
                "status_code": response.status,
                "body": parsed,
            }
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text
        return {
            "status_code": exc.code,
            "body": parsed,
        }


def _risk_input(req: ToolGatewayRequest) -> dict[str, Any]:
    data: dict[str, Any] = {
        "payload": req.payload,
        "context": req.risk_context,
    }
    if req.ai_review is not None:
        data["ai_review"] = req.ai_review
    return data


def _dispatch_risk_validate(req: ToolGatewayRequest) -> dict[str, Any]:
    return _json_success(req.request_id, validate_risk_gates(_risk_input(req)))


def _dispatch_backend_health(req: ToolGatewayRequest) -> dict[str, Any]:
    base_url = _backend_base_url(req.options)
    if not _is_local_backend(base_url) and not req.options.get("allow_external_backend", False):
        return _json_error(
            req.request_id,
            "EXTERNAL_BACKEND_NOT_ALLOWED",
            {"backend_url": base_url},
        )
    timeout = float(req.options.get("timeout_seconds", 10.0))
    return _json_success(req.request_id, _http_json("GET", f"{base_url}/health", timeout=timeout))


def _dispatch_backend_m8(req: ToolGatewayRequest) -> dict[str, Any]:
    if not req.options.get("skip_risk_gate", False):
        risk_result = validate_risk_gates(_risk_input(req))
        if not risk_result.get("ok"):
            return _json_error(
                req.request_id,
                "RISK_GATE_REJECTED",
                risk_result,
                status="rejected",
            )

    base_url = _backend_base_url(req.options)
    if not _is_local_backend(base_url) and not req.options.get("allow_external_backend", False):
        return _json_error(
            req.request_id,
            "EXTERNAL_BACKEND_NOT_ALLOWED",
            {"backend_url": base_url},
        )

    endpoint = str(req.options.get("endpoint") or "/webhook/m8")
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    timeout = float(req.options.get("timeout_seconds", 10.0))
    response = _http_json("POST", f"{base_url}{endpoint}", req.payload, timeout=timeout)
    ok = 200 <= int(response["status_code"]) < 300
    if not ok:
        return _json_error(req.request_id, "BACKEND_REQUEST_FAILED", response)
    return _json_success(req.request_id, response)


def _run_module_main(module_name: str, callable_name: str) -> dict[str, Any]:
    module = importlib.import_module(module_name)
    target: Callable[[], Any] = getattr(module, callable_name)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = target()
    return {
        "module": module_name,
        "callable": callable_name,
        "return_value": result,
        "stdout": buffer.getvalue(),
    }


def _dispatch_expensive_module(req: ToolGatewayRequest, tool_name: str) -> dict[str, Any]:
    if not req.options.get("allow_expensive", False):
        return _json_error(
            req.request_id,
            "EXPENSIVE_TOOL_REQUIRES_ALLOW_FLAG",
            {
                "tool": tool_name,
                "required_option": "allow_expensive=true",
            },
        )
    module_name, callable_name = EXPENSIVE_MODULE_TOOLS[tool_name]
    try:
        return _json_success(req.request_id, _run_module_main(module_name, callable_name))
    except Exception as exc:
        return _json_error(
            req.request_id,
            "MODULE_EXECUTION_FAILED",
            {
                "tool": tool_name,
                "module": module_name,
                "error": str(exc),
            },
        )


def _dispatch_quality_check(req: ToolGatewayRequest) -> dict[str, Any]:
    try:
        return _json_success(req.request_id, _run_module_main("app.scripts.quality_check", "main"))
    except Exception as exc:
        return _json_error(req.request_id, "QUALITY_CHECK_FAILED", str(exc))


def _dispatch_trade_report(req: ToolGatewayRequest) -> dict[str, Any]:
    if not req.options.get("allow_network", False):
        return _json_error(
            req.request_id,
            "NETWORK_TOOL_REQUIRES_ALLOW_FLAG",
            {
                "tool": "trade.report",
                "required_option": "allow_network=true",
            },
        )

    extra_path = (
        req.options.get("module_path")
        or os.getenv("GATEWAY_TRADE_ANALYZER_PATH")
        or "G:\\Scripter"
    )
    if extra_path and extra_path not in sys.path:
        sys.path.insert(0, str(extra_path))

    api_key = os.getenv("PIONEX_API_KEY", "")
    api_secret = os.getenv("PIONEX_API_SECRET", "")
    if not api_key or not api_secret:
        return _json_error(
            req.request_id,
            "PIONEX_CREDENTIALS_MISSING",
            "PIONEX_API_KEY and PIONEX_API_SECRET are required for trade.report.",
        )

    try:
        from pionex_api import PionexClient
        from trade_analyzer import TradeAnalyzer

        symbol = str(req.payload.get("symbol", "BTC_USDT"))
        account = str(req.payload.get("account", "spot"))
        days = int(req.payload.get("days", 30))
        client = PionexClient(api_key=api_key, api_secret=api_secret)
        report = TradeAnalyzer(client=client, symbol=symbol).generate_report(
            account=account,
            days=days,
        )
        return _json_success(
            req.request_id,
            {
                "symbol": symbol,
                "account": account,
                "days": days,
                "report": report,
            },
        )
    except Exception as exc:
        return _json_error(req.request_id, "TRADE_REPORT_FAILED", str(exc))


DISPATCHERS: dict[str, Callable[[ToolGatewayRequest], dict[str, Any]]] = {
    "risk.validate": _dispatch_risk_validate,
    "backend.health": _dispatch_backend_health,
    "backend.m8": _dispatch_backend_m8,
    "quality.check": _dispatch_quality_check,
    "trade.report": _dispatch_trade_report,
}


def dispatch_tool_request(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and dispatch one Gem tool request through the allowlist."""
    try:
        req = ToolGatewayRequest.model_validate(raw)
    except ValidationError as exc:
        return _json_error(
            None,
            "GATEWAY_REQUEST_SCHEMA_INVALID",
            json.loads(exc.json()),
        )

    tool_name = _normalize_tool(req.tool)
    if not tool_name:
        return _json_error(
            req.request_id,
            "UNKNOWN_TOOL",
            {
                "tool": req.tool,
                "allowed_tools": sorted(TOOL_ALIASES),
            },
        )

    if tool_name in EXPENSIVE_MODULE_TOOLS:
        return _dispatch_expensive_module(req, tool_name)

    dispatcher = DISPATCHERS.get(tool_name)
    if dispatcher is None:
        return _json_error(req.request_id, "TOOL_NOT_IMPLEMENTED", tool_name)
    return dispatcher(req)


def _read_json_input(path: str | None) -> dict[str, Any]:
    raw = sys.stdin.read() if not path or path == "-" else open(path, encoding="utf-8").read()
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch a validated Gem JSON tool request.")
    parser.add_argument("--input", "-i", default="-", help="JSON file path, or '-' for stdin.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    try:
        raw = _read_json_input(args.input)
        result = dispatch_tool_request(raw)
    except (json.JSONDecodeError, OSError) as exc:
        result = _json_error(None, "INVALID_JSON", str(exc))

    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
