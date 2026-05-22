from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReferenceDecision(str, Enum):
    ADOPT = "adopt"
    ADAPT_OFFLINE = "adapt_offline"
    EXCLUDE = "exclude"


@dataclass(frozen=True)
class ReferenceSource:
    source_id: str
    source_type: str
    domains: tuple[str, ...]
    decision: ReferenceDecision
    production_dependency: bool
    training_allowed: bool
    confidence: str
    benefit: str
    risks: tuple[str, ...]
    actions: tuple[str, ...]


REFERENCE_SOURCES: tuple[ReferenceSource, ...] = (
    ReferenceSource(
        source_id="parameter_sensitivity_sharpe",
        source_type="research_note",
        domains=("parameter_sensitivity", "risk", "backtest_review"),
        decision=ReferenceDecision.ADAPT_OFFLINE,
        production_dependency=False,
        training_allowed=True,
        confidence="medium",
        benefit="Useful parameter priors for offline experiments.",
        risks=("Reported metrics are hypotheses until reproduced on clean exchange data.",),
        actions=(
            "Use as GA seed ranges only.",
            "Require clean-data replay before any release claim.",
        ),
    ),
    ReferenceSource(
        source_id="binance_ethusdt_perp_5m_to_csv",
        source_type="python_data_ingestion",
        domains=("binance_futures", "data_import", "ohlcv"),
        decision=ReferenceDecision.ADOPT,
        production_dependency=False,
        training_allowed=True,
        confidence="high",
        benefit="Clean pattern for USD-M futures kline pagination and CSV export.",
        risks=("Network calls must stay explicit and offline-research scoped.",),
        actions=(
            "Port request construction into the offline research layer.",
            "Mock HTTP in tests; never call Binance during unit tests.",
        ),
    ),
    ReferenceSource(
        source_id="bitcoin_trading_sim",
        source_type="python_simulation",
        domains=("synthetic_data", "strategy_sketch"),
        decision=ReferenceDecision.EXCLUDE,
        production_dependency=False,
        training_allowed=False,
        confidence="high",
        benefit="Useful only as a warning example for synthetic-performance traps.",
        risks=("Synthetic prices and future-looking logic make metrics unusable.",),
        actions=("Do not train production logic or performance claims from this file.",),
    ),
    ReferenceSource(
        source_id="genetic_optimizer",
        source_type="python_optimizer",
        domains=("genetic_algorithm", "parameter_search"),
        decision=ReferenceDecision.ADAPT_OFFLINE,
        production_dependency=False,
        training_allowed=True,
        confidence="medium",
        benefit="Reusable GA structure for population, mutation, crossover, and elites.",
        risks=("Synthetic backtest numbers must not be used as evidence.",),
        actions=(
            "Reuse optimizer structure only.",
            "Plug into clean Binance/Pionex-compatible datasets before scoring.",
        ),
    ),
    ReferenceSource(
        source_id="mtf_cisd_complete_framework",
        source_type="python_backtest_framework",
        domains=("mtf", "cisd", "walk_forward", "monte_carlo"),
        decision=ReferenceDecision.ADAPT_OFFLINE,
        production_dependency=False,
        training_allowed=True,
        confidence="medium",
        benefit="Good architecture seed for StrategyConfig, CISD, WFO, and Monte Carlo validation.",
        risks=("MTF behavior must use real timeframe resampling, not local state shifts.",),
        actions=(
            "Move concepts into offline research modules.",
            "Replace synthetic data paths with exchange-data fixtures.",
        ),
    ),
    ReferenceSource(
        source_id="test_v4_logic",
        source_type="python_test_reference",
        domains=("pionex", "pine", "safety_invariants"),
        decision=ReferenceDecision.ADOPT,
        production_dependency=False,
        training_allowed=True,
        confidence="high",
        benefit="Strong source for secret-free Pionex and TradingView invariant tests.",
        risks=("Original hardcoded paths and UUID-like values must not be preserved.",),
        actions=(
            "Convert intent into pytest fixtures.",
            "Assert dry-run defaults, live gates, schema strictness, and no secrets.",
        ),
    ),
    ReferenceSource(
        source_id="desktop_app",
        source_type="python_operator_ui",
        domains=("operator_console", "status_ui", "kill_switch"),
        decision=ReferenceDecision.ADAPT_OFFLINE,
        production_dependency=False,
        training_allowed=True,
        confidence="medium",
        benefit="Useful future operator-console ideas for status, toggles, and emergency control.",
        risks=("Legacy relay coupling and external-execution controls need fresh gating.",),
        actions=("Keep out of V1 execution core; revisit after API release candidate.",),
    ),
    ReferenceSource(
        source_id="llm_attacks_readme",
        source_type="empty_readme",
        domains=("security_review",),
        decision=ReferenceDecision.EXCLUDE,
        production_dependency=False,
        training_allowed=False,
        confidence="high",
        benefit="No usable project content found.",
        risks=("No stable signal to extract.",),
        actions=("Exclude from this framework corpus.",),
    ),
    ReferenceSource(
        source_id="wallet_generator_pdf",
        source_type="wallet_security_document",
        domains=("wallet_security", "secrets_hygiene"),
        decision=ReferenceDecision.EXCLUDE,
        production_dependency=False,
        training_allowed=False,
        confidence="high",
        benefit="Only yields a security hygiene rule: never ingest wallet/key material.",
        risks=("Contains private-key example material and must not enter logs or training data.",),
        actions=("Exclude from corpus; preserve only the no-wallet-secrets rule.",),
    ),
)


def get_source(source_id: str) -> ReferenceSource:
    for source in REFERENCE_SOURCES:
        if source.source_id == source_id:
            return source
    raise KeyError(f"Unknown reference source: {source_id}")


def sources_by_decision(decision: ReferenceDecision) -> tuple[ReferenceSource, ...]:
    return tuple(source for source in REFERENCE_SOURCES if source.decision == decision)


def training_sources() -> tuple[ReferenceSource, ...]:
    return tuple(source for source in REFERENCE_SOURCES if source.training_allowed)


def excluded_sources() -> tuple[ReferenceSource, ...]:
    return sources_by_decision(ReferenceDecision.EXCLUDE)


def production_dependencies() -> tuple[ReferenceSource, ...]:
    return tuple(source for source in REFERENCE_SOURCES if source.production_dependency)

