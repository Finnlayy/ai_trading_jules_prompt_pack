from app.services.signal_generator import OHLCV, SignalGenerator


class FakeFeed:
    def fetch(self, _symbol: str, bars: int):
        return [
            OHLCV(
                ts=1_700_000_000_000 + index * 60_000,
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

