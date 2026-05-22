import pytest

from app.research.binance_futures_data import (
    BinanceFuturesKlineRequest,
    build_research_report,
    build_kline_params,
    fetch_klines_paginated,
    kline_to_record,
    normalize_symbol,
)


def test_normalize_symbol_accepts_pionex_style_separator():
    assert normalize_symbol("eth_usdt") == "ETHUSDT"


def test_build_kline_params_validates_research_request():
    params = build_kline_params(
        symbol="ETH_USDT",
        interval="5m",
        start_time_ms=1_700_000_000_000,
        end_time_ms=1_700_000_300_000,
        limit=500,
    )

    assert params == {
        "symbol": "ETHUSDT",
        "interval": "5m",
        "limit": 500,
        "startTime": 1_700_000_000_000,
        "endTime": 1_700_000_300_000,
    }


def test_build_kline_params_rejects_unsupported_interval():
    with pytest.raises(ValueError, match="Unsupported interval"):
        build_kline_params(symbol="ETHUSDT", interval="2m")


def test_request_dataclass_uses_same_param_contract():
    request = BinanceFuturesKlineRequest(symbol="btcusdt", interval="1h", limit=10)

    assert request.to_params() == {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "limit": 10,
    }


def test_kline_to_record_maps_binance_payload():
    record = kline_to_record(
        [
            1,
            "100.0",
            "110.0",
            "95.0",
            "105.0",
            "12.5",
            2,
            "1300.0",
            42,
            "6.0",
            "650.0",
            "0",
        ]
    )

    assert record["open_time"] == 1
    assert record["close"] == 105.0
    assert record["number_of_trades"] == 42


def test_fetch_klines_paginated_advances_cursor_without_network():
    class FakeResponse:
        def __init__(self, rows):
            self._rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return self._rows

    class FakeSession:
        def __init__(self):
            self.calls = []

        def get(self, _url, params, timeout):
            self.calls.append((params.copy(), timeout))
            start = params["startTime"]
            if len(self.calls) == 1:
                return FakeResponse(
                    [
                        [
                            start + (index * 60_000),
                            "1",
                            "2",
                            "0.5",
                            "1.5",
                            "10",
                            start + (index * 60_000) + 59_999,
                            "15",
                            1,
                            "5",
                            "7",
                        ]
                        for index in range(1000)
                    ]
                )
            return FakeResponse(
                [
                    [start, "2", "4", "1.5", "3", "12", start + 59_999, "30", 3, "7", "9"],
                ]
            )

    session = FakeSession()

    records = fetch_klines_paginated(
        symbol="ETHUSDT",
        interval="1m",
        start_time_ms=1_700_000_000_000,
        max_rows=1001,
        session=session,
        sleep_seconds=0,
    )

    assert len(records) == 1001
    assert records[-1]["open_time"] == 1_700_060_000_000
    assert session.calls[1][0]["startTime"] == 1_700_060_000_000


def test_build_research_report_includes_resample_based_mtf_summary():
    records = [
        {
            "open_time": index * 60_000,
            "open": 100 + index,
            "high": 102 + index,
            "low": 99 + index,
            "close": 101 + index,
            "volume": 10,
            "close_time": (index + 1) * 60_000 - 1,
            "quote_asset_volume": 1000,
            "number_of_trades": 10,
            "taker_buy_base_volume": 5,
            "taker_buy_quote_volume": 500,
        }
        for index in range(4)
    ]

    report = build_research_report(records, symbol="eth_usdt", interval="1m", timeframes=(2,))

    assert report["symbol"] == "ETHUSDT"
    assert report["records"] == 4
    assert report["mtf_cisd"]["timeframes"] == [2]
