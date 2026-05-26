from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid

class Badge(BaseModel):
    name: str
    description: str
    icon: str
    awarded_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class CareerEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scout_name: str
    event_type: str  # "first_call", "first_win", "badge_earned", "prompt_evolution", "ab_test", "prediction_result"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    details: Dict[str, Any] = Field(default_factory=dict)

class ScoutIdentity(BaseModel):
    scout_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    archetype: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
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

class AgentLeaderboardEntry(BaseModel):
    scout_name: str
    accuracy: float
    experience: int
    specialization_score: float
    top_badge: Optional[Badge] = None
