from app.services.signal_generator import OHLCV, SignalGenerator


START_TS = 1_700_000_000_000


class FakeFeed:
    def fetch(self, _symbol: str, bars: int, timeframe: str = "1m"):
        return [
            OHLCV(
                ts=START_TS + index * 60_000,
                o=100.0 + index * 0.01,
                h=101.0 + index * 0.01,
                l=99.0 + index * 0.01,
                c=100.5 + index * 0.01,
                v=1000.0,
            )
            for index in range(bars)
        ]


class FakeScorer:
    def __init__(self, score: float):
        self.score = score

    def score_series(self, candles):
        return [
            {
                "confluence_score": self.score,
                "direction_hint": "LONG",
                "alignment_count": 2,
            }
            for _ in candles
        ]


def test_signal_generator_reports_threshold_diagnostics_when_no_payloads():
    generator = SignalGenerator(scorer=FakeScorer(score=5.0))
    generator.feed = FakeFeed()

    payloads = generator.generate_payloads(
        symbol="HYPEUSDT",
        bars=60,
        min_confluence=6.0,
    )

    assert payloads == []
    assert generator.last_generation_summary["min_confluence"] == 6.0
    assert generator.last_generation_summary["max_confluence_score"] == 5.0
    assert generator.last_generation_summary["payloads_generated"] == 0


def test_signal_generator_min_confluence_override_allows_simulation_payloads():
    generator = SignalGenerator(scorer=FakeScorer(score=6.0))
    generator.feed = FakeFeed()

    payloads = generator.generate_payloads(
        symbol="HYPEUSDT",
        bars=60,
        min_confluence=6.0,
    )

    assert payloads
    assert payloads[0].confluence_score == 6.0
    assert generator.last_generation_summary["payloads_generated"] == len(payloads)


def test_latest_candidate_uses_latest_closed_candle_only():
    generator = SignalGenerator(scorer=FakeScorer(score=6.0))
    generator.feed = FakeFeed()

    payload = generator.generate_latest_candidate(
        symbol="HYPEUSDT",
        timeframe="1m",
        bars=61,
        min_confluence=6.0,
        now_ms=START_TS + 60 * 60_000,
    )

    closed_ts = START_TS + 59 * 60_000
    assert payload is not None
    assert payload.signal_id.endswith(f"-{closed_ts}")
    assert payload.signal_id.startswith("live-HYPEUSDT-1m-")
    assert payload.bar_confirmed is True
    assert generator.last_generation_summary["mode"] == "latest_candidate"
    assert generator.last_generation_summary["last_closed_bar_ts"] == closed_ts
    assert generator.last_generation_summary["candidate_generated"] is True


def test_latest_candidate_skips_already_processed_candle():
    generator = SignalGenerator(scorer=FakeScorer(score=6.0))
    generator.feed = FakeFeed()
    closed_ts = START_TS + 59 * 60_000

    payload = generator.generate_latest_candidate(
        symbol="HYPEUSDT",
        timeframe="1m",
        bars=60,
        min_confluence=6.0,
        last_processed_ts=closed_ts,
        now_ms=START_TS + 60 * 60_000,
    )

    assert payload is None
    assert generator.last_generation_summary["last_closed_bar_ts"] == closed_ts
    assert generator.last_generation_summary["candidate_generated"] is False
    assert generator.last_generation_summary["message"] == "Latest closed candle already processed"


def test_latest_candidate_skips_when_latest_closed_bar_has_no_signal():
    generator = SignalGenerator(scorer=FakeScorer(score=5.0))
    generator.feed = FakeFeed()

    payload = generator.generate_latest_candidate(
        symbol="HYPEUSDT",
        timeframe="1m",
        bars=60,
        min_confluence=6.0,
        now_ms=START_TS + 60 * 60_000,
    )

    assert payload is None
    assert generator.last_generation_summary["candidate_generated"] is False
    assert generator.last_generation_summary["latest_confluence_score"] == 5.0

