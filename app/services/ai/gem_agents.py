from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    display_name: str
    phase_id: int | None
    archetype: str
    personality_vector: dict[str, float]
    drill_type: str


LEGACY_SCOUT_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        name="technical",
        display_name="Technical Scout",
        phase_id=None,
        archetype="Analyst",
        personality_vector={"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.8},
        drill_type="pattern_recognition",
    ),
    AgentDefinition(
        name="sentiment",
        display_name="Sentiment Scout",
        phase_id=None,
        archetype="Diplomat",
        personality_vector={"analytical": 0.3, "cautious": 0.5, "momentum_driven": 0.9},
        drill_type="sentiment_analysis",
    ),
    AgentDefinition(
        name="risk",
        display_name="Risk Scout",
        phase_id=None,
        archetype="Guardian",
        personality_vector={"analytical": 0.8, "cautious": 0.95, "momentum_driven": 0.1},
        drill_type="crisis_detection",
    ),
    AgentDefinition(
        name="macro",
        display_name="Macro Scout",
        phase_id=None,
        archetype="Strategist",
        personality_vector={"analytical": 0.7, "cautious": 0.7, "momentum_driven": 0.5},
        drill_type="regime_identification",
    ),
    AgentDefinition(
        name="execution",
        display_name="Execution Scout",
        phase_id=None,
        archetype="Operator",
        personality_vector={"analytical": 0.9, "cautious": 0.8, "momentum_driven": 0.2},
        drill_type="execution_quality",
    ),
    AgentDefinition(
        name="correlation",
        display_name="Correlation Scout",
        phase_id=None,
        archetype="Architect",
        personality_vector={"analytical": 0.85, "cautious": 0.85, "momentum_driven": 0.1},
        drill_type="correlation_risk",
    ),
)


GEM_AGENT_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        name="macro_sentinel",
        display_name="Macro Sentinel",
        phase_id=1,
        archetype="Strategist",
        personality_vector={"analytical": 0.75, "cautious": 0.75, "momentum_driven": 0.25},
        drill_type="regime_identification",
    ),
    AgentDefinition(
        name="market_dna",
        display_name="Market DNA Sequencer",
        phase_id=2,
        archetype="Analyst",
        personality_vector={"analytical": 0.95, "cautious": 0.45, "momentum_driven": 0.7},
        drill_type="market_quality",
    ),
    AgentDefinition(
        name="structural_architect",
        display_name="Structural Architect",
        phase_id=3,
        archetype="Architect",
        personality_vector={"analytical": 0.9, "cautious": 0.6, "momentum_driven": 0.45},
        drill_type="structure_mapping",
    ),
    AgentDefinition(
        name="harmony_coordinator",
        display_name="Harmony Index Coordinator",
        phase_id=4,
        archetype="Coordinator",
        personality_vector={"analytical": 0.75, "cautious": 0.7, "momentum_driven": 0.45},
        drill_type="mtf_alignment",
    ),
    AgentDefinition(
        name="indicator_fusion",
        display_name="Indicator Fusion Engine",
        phase_id=5,
        archetype="Analyst",
        personality_vector={"analytical": 0.9, "cautious": 0.55, "momentum_driven": 0.65},
        drill_type="indicator_confluence",
    ),
    AgentDefinition(
        name="risk_kernel",
        display_name="Risk & Capital Kernel",
        phase_id=6,
        archetype="Guardian",
        personality_vector={"analytical": 0.9, "cautious": 0.98, "momentum_driven": 0.1},
        drill_type="crisis_detection",
    ),
    AgentDefinition(
        name="pine_core",
        display_name="Pine Script v6 Core Developer",
        phase_id=7,
        archetype="Developer",
        personality_vector={"analytical": 0.9, "cautious": 0.65, "momentum_driven": 0.25},
        drill_type="strategy_code_review",
    ),
    AgentDefinition(
        name="payload_qa",
        display_name="Payload & QA Integrator",
        phase_id=8,
        archetype="Verifier",
        personality_vector={"analytical": 0.95, "cautious": 0.95, "momentum_driven": 0.1},
        drill_type="payload_validation",
    ),
    AgentDefinition(
        name="execution_watchdog",
        display_name="Execution Watchdog",
        phase_id=9,
        archetype="Operator",
        personality_vector={"analytical": 0.9, "cautious": 0.9, "momentum_driven": 0.2},
        drill_type="execution_quality",
    ),
    AgentDefinition(
        name="evolution_optimizer",
        display_name="Evolution Optimizer",
        phase_id=10,
        archetype="Researcher",
        personality_vector={"analytical": 0.85, "cautious": 0.5, "momentum_driven": 0.45},
        drill_type="learning_feedback",
    ),
)


LEGACY_SCOUT_NAMES = tuple(agent.name for agent in LEGACY_SCOUT_DEFINITIONS)
GEM_AGENT_NAMES = tuple(agent.name for agent in GEM_AGENT_DEFINITIONS)
DEFAULT_AGENT_DEFINITIONS = LEGACY_SCOUT_DEFINITIONS + GEM_AGENT_DEFINITIONS
DEFAULT_AGENT_NAMES = tuple(agent.name for agent in DEFAULT_AGENT_DEFINITIONS)
AGENT_DEFINITIONS_BY_NAME = {agent.name: agent for agent in DEFAULT_AGENT_DEFINITIONS}


def get_agent_definition(name: str) -> AgentDefinition | None:
    return AGENT_DEFINITIONS_BY_NAME.get(name)
