from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import uuid

class Badge(BaseModel):
    name: str
    description: str
    icon: str
    awarded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class CareerEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scout_name: str
    event_type: str  # "first_call", "first_win", "badge_earned", "prompt_evolution", "ab_test", "prediction_result"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = Field(default_factory=dict)

class ScoutIdentity(BaseModel):
    scout_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    archetype: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    born_from: str = "v1_base"
    generation: int = 1
    specialization_symbols: List[str] = Field(default_factory=list)
    badges: List[Badge] = Field(default_factory=list)
    personality_vector: Dict[str, float] = Field(default_factory=dict)

    # Stats for UI
    total_calls: int = 0
    correct_calls: int = 0
    accuracy: float = 0.0
    current_streak: int = 0
    confidence_level: float = Field(default=0.5, ge=0.0, le=1.0)
    experience_level: str = Field(default="Novice")

class AgentLeaderboardEntry(BaseModel):
    scout_name: str
    accuracy: float
    experience: int
    specialization_score: float
    top_badge: Optional[Badge] = None


class SyntheticDrill(BaseModel):
    drill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drill_type: str  # "pattern_recognition", "crisis_detection", "sentiment_analysis", "regime_identification"
    scout_target: str # Which scout this drill is for
    scenario_data: Dict[str, Any]  # The mock historical payload/data
    expected_outcome: Any  # The true historical outcome to check against
    difficulty: int = 1

class DrillResult(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drill_id: str
    scout_name: str
    scout_decision: Any
    is_correct: bool
    confidence: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    feedback_notes: str = ""

class PromptVersion(BaseModel):
    version_id: str
    scout_name: str
    prompt_text: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parent_version: Optional[str] = None
    change_summary: str = "Initial version"

class ABTest(BaseModel):
    test_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scout_name: str
    variant_a_version: str
    variant_b_version: str
    status: str = "running" # "running", "concluded"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    concluded_at: Optional[str] = None
    calls_a: int = 0
    calls_b: int = 0
    correct_a: int = 0
    correct_b: int = 0
    winner_version: Optional[str] = None

class CurriculumProgress(BaseModel):
    scout_name: str
    curriculum_level: str # "Beginner", "Intermediate", "Advanced", "Master"
    completed_drills: int = 0
    required_drills: int = 10
    passed_drills: int = 0
    average_confidence: float = 0.0

class DiversityMonitorStats(BaseModel):
    agreement_rate: float = 0.0
    total_evaluations: int = 0
    high_agreement_warnings: int = 0
    low_agreement_warnings: int = 0
    status: str = "optimal" # "optimal", "echo_chamber", "divergent"
