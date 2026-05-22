from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import requests

from app.research.mtf_cisd import candles_from_records, summarize_mtf_cisd


BINANCE_FAPI_BASE_URL = "https://fapi.binance.com"
KLINE_ENDPOINT = "/fapi/v1/klines"
MAX_KLINE_LIMIT = 1000

INTERVAL_TO_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

CSV_HEADERS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
)

DEFAULT_OUTPUT_DIR = Path("app/scripts/data_cache")
DEFAULT_REPORT_DIR = Path("app/scripts/optimizer_results")


@dataclass(frozen=True)
class BinanceFuturesKlineRequest:
    symbol: str
    interval: str
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    limit: int = MAX_KLINE_LIMIT

    def to_params(self) -> dict[str, Any]:
        return build_kline_params(
            symbol=self.symbol,
            interval=self.interval,
            start_time_ms=self.start_time_ms,
            end_time_ms=self.end_time_ms,
            limit=self.limit,
        )


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("_", "")
    if not normalized:
        raise ValueError("symbol is required")
    return normalized


def parse_utc_datetime(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def datetime_to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def build_kline_params(
    symbol: str,
    interval: str,
    start_time_ms: int | None = None,
    end_time_ms: int | None = None,
    limit: int = MAX_KLINE_LIMIT,
) -> dict[str, Any]:
    normalized_interval = interval.strip()
    if normalized_interval not in INTERVAL_TO_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    if limit < 1 or limit > MAX_KLINE_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_KLINE_LIMIT}")
    if start_time_ms is not None and end_time_ms is not None and start_time_ms > end_time_ms:
        raise ValueError("start_time_ms must be before end_time_ms")

    params: dict[str, Any] = {
        "symbol": normalize_symbol(symbol),
        "interval": normalized_interval,
        "limit": limit,
    }
    if start_time_ms is not None:
        params["startTime"] = start_time_ms
    if end_time_ms is not None:
        params["endTime"] = end_time_ms
    return params


def kline_to_record(kline: list[Any]) -> dict[str, Any]:
    if len(kline) < 11:
        raise ValueError("Binance kline row must contain at least 11 fields")
    return {
        "open_time": int(kline[0]),
        "open": float(kline[1]),
        "high": float(kline[2]),
        "low": float(kline[3]),
        "close": float(kline[4]),
        "volume": float(kline[5]),
        "close_time": int(kline[6]),
        "quote_asset_volume": float(kline[7]),
        "number_of_trades": int(kline[8]),
        "taker_buy_base_volume": float(kline[9]),
        "taker_buy_quote_volume": float(kline[10]),
    }


def _dedupe_sort_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped = {int(record["open_time"]): dict(record) for record in records}
    return [deduped[open_time] for open_time in sorted(deduped)]


def fetch_klines(
    request: BinanceFuturesKlineRequest,
    session: requests.Session | None = None,
    base_url: str = BINANCE_FAPI_BASE_URL,
) -> list[dict[str, Any]]:
    """Fetch klines for explicit offline research runs.

    This function is deliberately not used by the live broker path.
    Unit tests should pass a fake session and must not depend on the network.
    """
    http = session or requests.Session()
    response = http.get(
        f"{base_url.rstrip('/')}{KLINE_ENDPOINT}",
        params=request.to_params(),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Unexpected Binance kline response")
    return [kline_to_record(row) for row in payload]


def fetch_klines_paginated(
    symbol: str,
    interval: str,
    start_time_ms: int,
    end_time_ms: int | None = None,
    max_rows: int | None = None,
    session: requests.Session | None = None,
    base_url: str = BINANCE_FAPI_BASE_URL,
    sleep_seconds: float = 0.08,
) -> list[dict[str, Any]]:
    normalized_interval = interval.strip()
    if normalized_interval not in INTERVAL_TO_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    if max_rows is not None and max_rows < 1:
        raise ValueError("max_rows must be positive when provided")

    http = session or requests.Session()
    cursor = start_time_ms
    collected: list[dict[str, Any]] = []
    interval_ms = INTERVAL_TO_MS[normalized_interval]

    while True:
        remaining = None if max_rows is None else max_rows - len(collected)
        if remaining is not None and remaining <= 0:
            break
        limit = MAX_KLINE_LIMIT if remaining is None else min(MAX_KLINE_LIMIT, remaining)
        request = BinanceFuturesKlineRequest(
            symbol=symbol,
            interval=normalized_interval,
            start_time_ms=cursor,
            end_time_ms=end_time_ms,
            limit=limit,
        )
        chunk = fetch_klines(request=request, session=http, base_url=base_url)
        if not chunk:
            break
        collected.extend(chunk)

        last_open = int(chunk[-1]["open_time"])
        next_cursor = last_open + interval_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor

        if end_time_ms is not None and cursor > end_time_ms:
            break
        if len(chunk) < limit:
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return _dedupe_sort_records(collected)


def write_csv(records: Iterable[Mapping[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for record in records:
            writer.writerow({header: record.get(header, "") for header in CSV_HEADERS})


def default_output_path(symbol: str, interval: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"{normalize_symbol(symbol)}_{interval}_{stamp}.csv"


def _parse_time_arg(value: str | None) -> int | None:
    if not value:
        return None
    return datetime_to_ms(parse_utc_datetime(value))


def _parse_timeframes(value: str) -> tuple[int, ...]:
    timeframes = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not timeframes:
        raise argparse.ArgumentTypeError("at least one timeframe is required")
    if any(timeframe <= 0 for timeframe in timeframes):
        raise argparse.ArgumentTypeError("timeframes must be positive minutes")
    return timeframes


def build_research_report(
    records: list[dict[str, Any]],
    symbol: str,
    interval: str,
    timeframes: tuple[int, ...],
) -> dict[str, Any]:
    candles = candles_from_records(records)
    report = summarize_mtf_cisd(candles, timeframes=timeframes)
    return {
        "symbol": normalize_symbol(symbol),
        "interval": interval,
        "records": len(records),
        "mtf_cisd": report,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Binance USD-M futures klines for offline research.",
    )
    parser.add_argument("--symbol", default="ETHUSDT", help="Binance futures symbol, e.g. ETHUSDT")
    parser.add_argument("--interval", default="5m", choices=sorted(INTERVAL_TO_MS), help="Kline interval")
    parser.add_argument("--start", help="UTC start timestamp, e.g. 2026-01-01T00:00:00Z")
    parser.add_argument("--end", help="UTC end timestamp, e.g. 2026-02-01T00:00:00Z")
    parser.add_argument("--bars", type=int, default=1000, help="Maximum bars to fetch when --start is omitted")
    parser.add_argument("--out", type=Path, help="CSV output path")
    parser.add_argument("--base-url", default=BINANCE_FAPI_BASE_URL, help="Binance USD-M futures API base URL")
    parser.add_argument("--sleep-seconds", type=float, default=0.08, help="Pause between paginated calls")
    parser.add_argument(
        "--mtf-report",
        type=Path,
        help="Optional JSON report path for resample-based MTF/CISD summary",
    )
    parser.add_argument(
        "--mtf-timeframes",
        type=_parse_timeframes,
        default=(5, 15, 60, 240),
        help="Comma-separated timeframe minutes for MTF/CISD report",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    interval_ms = INTERVAL_TO_MS[args.interval]
    end_time_ms = _parse_time_arg(args.end) or int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time_ms = _parse_time_arg(args.start)
    if start_time_ms is None:
        if args.bars < 1:
            parser.error("--bars must be positive")
        start_time_ms = end_time_ms - (args.bars * interval_ms)
    if start_time_ms > end_time_ms:
        parser.error("--start must be before --end")

    records = fetch_klines_paginated(
        symbol=args.symbol,
        interval=args.interval,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        max_rows=args.bars,
        base_url=args.base_url,
        sleep_seconds=args.sleep_seconds,
    )
    out_path = args.out or default_output_path(args.symbol, args.interval)
    write_csv(records, out_path)
    print(f"Wrote {len(records)} Binance futures klines to {out_path}")

    if args.mtf_report:
        report = build_research_report(
            records=records,
            symbol=args.symbol,
            interval=args.interval,
            timeframes=args.mtf_timeframes,
        )
        args.mtf_report.parent.mkdir(parents=True, exist_ok=True)
        args.mtf_report.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"Wrote MTF/CISD research report to {args.mtf_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
