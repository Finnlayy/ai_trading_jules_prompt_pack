from app.research.reference_corpus import (
    ReferenceDecision,
    excluded_sources,
    get_source,
    production_dependencies,
    sources_by_decision,
    training_sources,
)


def test_reference_corpus_keeps_runtime_dependency_boundary():
    assert production_dependencies() == ()


def test_high_value_sources_are_available_for_research_training():
    source_ids = {source.source_id for source in training_sources()}

    assert "binance_ethusdt_perp_5m_to_csv" in source_ids
    assert "mtf_cisd_complete_framework" in source_ids
    assert "test_v4_logic" in source_ids


def test_sensitive_or_low_signal_sources_are_excluded():
    excluded = {source.source_id for source in excluded_sources()}

    assert "wallet_generator_pdf" in excluded
    assert "llm_attacks_readme" in excluded
    assert "bitcoin_trading_sim" in excluded
    assert get_source("wallet_generator_pdf").training_allowed is False


def test_adapt_offline_sources_are_not_promoted_to_production():
    for source in sources_by_decision(ReferenceDecision.ADAPT_OFFLINE):
        assert source.production_dependency is False
        assert source.actions

