from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Optional, Any, Literal
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


class AcademyPolicyState(BaseModel):
    state_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feature_version: str = "academy_policy_state_v1"
    scout_names: List[str]
    feature_names: List[str]
    observation: List[float]
    observation_size: int
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AcademyPolicyAction(BaseModel):
    raw_action: List[int]
    scout_index: int
    scout_name: str
    drill_profile: str
    difficulty: int = Field(ge=1, le=4)
    prompt_action: str
    curriculum_action: str
    sampling_strategy: str
    ab_allocation: str
    evolution_action: str
    degraded: bool = False
    fallback_reason: Optional[str] = None


class AcademyPolicyDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mode: str
    backend: str
    source: str
    action: AcademyPolicyAction
    state_feature_version: str = "academy_policy_state_v1"
    model_id: Optional[str] = None
    executed: bool = True
    fallback_reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AcademyPolicyRewardBreakdown(BaseModel):
    accuracy_delta: float = 0.0
    calibration_delta: float = 0.0
    curriculum_delta: float = 0.0
    ab_lift: float = 0.0
    specialization_delta: float = 0.0
    diversity_health: float = 0.0
    echo_penalty: float = 0.0
    divergence_penalty: float = 0.0
    regression_penalty: float = 0.0
    invalid_action_penalty: float = 0.0
    total_reward: float = 0.0


class AcademyPolicyStatus(BaseModel):
    mode: str
    backend: str
    healthy: bool
    fallback_available: bool = True
    active_model_id: Optional[str] = None
    model_dir: str
    last_fallback_reason: Optional[str] = None
    scout_count: int
    observation_size: int
    action_space: List[int]
    python_runtime: str


class AcademyPolicyPreviewRequest(BaseModel):
    training_status: Dict[str, Any] = Field(default_factory=dict)
    count: int = Field(default=1, ge=1, le=16)


class AcademyBacktestRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    timestamp: Optional[str] = None
    close: float = Field(gt=0)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    scout_index: int = Field(default=0, ge=0)
    difficulty: int = Field(default=1, ge=0)
    total_reward: float = 0.0
    accuracy: float = 0.0
    calibration: float = 0.0
    ab_lift: float = 0.0


class AcademyBacktestingRunRequest(BaseModel):
    backend: Literal["backtrader", "vectorbt"] = "vectorbt"
    records: List[AcademyBacktestRecord] = Field(min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)


class AcademyBacktestingOptimizeRequest(BaseModel):
    records: List[AcademyBacktestRecord] = Field(min_length=1)
    initial_params: Dict[str, Any] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "sharpe": 1.0,
        "drawdown": 1.0,
        "calmar": 1.0,
    })
    method: Literal["differential_evolution", "minimize"] = "differential_evolution"
    maxiter: int = Field(default=10, ge=1, le=100)


class AcademyBacktestingGridSearchRequest(BaseModel):
    records: List[AcademyBacktestRecord] = Field(min_length=1)
    param_grid: Dict[str, List[Any]] = Field(min_length=1)


class AcademyBacktestingReportRequest(BaseModel):
    backend: Literal["backtrader", "vectorbt"] = "vectorbt"
    records: List[AcademyBacktestRecord] = Field(min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)
    include_charts: bool = True
