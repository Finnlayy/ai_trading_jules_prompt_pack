from fastapi import APIRouter
from app.services.agent_registry import agent_registry
from typing import List, Dict, Any

router = APIRouter(prefix="/academy", tags=["Academy"])

@router.get("/agents/registry")
def get_agents_registry():
    agents = agent_registry.get_all_identities()
    return {"agents": [a.model_dump() for a in agents]}

@router.get("/agents/{scout_id}/career")
def get_agent_career(scout_id: str):
    # Using scout_id as scout_name for now since that's what's tracked mostly
    entries = agent_registry.get_career_log(scout_id)
    return {"career": [e.model_dump() for e in entries]}

@router.get("/agents/leaderboard")
def get_leaderboard():
    agents = agent_registry.get_all_identities()

    leaderboard = []
    for agent in agents:
        top_badge = None
        if agent.badges:
            # Simple heuristic: last earned badge is often highest, or just pick one
            top_badge = agent.badges[-1].model_dump()

        leaderboard.append({
            "scout_name": agent.name,
            "archetype": agent.archetype,
            "accuracy": agent.accuracy,
            "experience": agent.total_calls,
            "specialization_score": 0.0, # Will be aggregated later if needed from ConfidenceRegistry
            "top_badge": top_badge,
            "badges": [b.model_dump() for b in agent.badges]
        })

    leaderboard.sort(key=lambda x: (x["accuracy"], x["experience"]), reverse=True)
    return {"leaderboard": leaderboard}

from app.services.training_drills import training_drills
from app.services.prompt_evolution import prompt_evolution
from app.services.ab_testing import ab_testing
from app.services.academy_curriculum import academy_curriculum
from app.schemas.academy import SyntheticDrill

@router.get("/drills/available")
def get_available_drills(scout_name: str, count: int = 5):
    drills = training_drills.generate_drills(scout_name, count)
    return {"drills": [d.model_dump() for d in drills]}

@router.post("/drill/evaluate")
async def evaluate_drill(drill: SyntheticDrill, scout_decision: str, confidence: float = 0.8):
    result = await training_drills.evaluate_drill(drill, scout_decision, confidence)
    academy_curriculum.record_drill_result(drill.scout_target, "Beginner", result.is_correct, result.confidence)
    return result.model_dump()

@router.get("/ab-tests")
def get_ab_tests():
    tests = ab_testing.get_all()
    return {"ab_tests": [t.model_dump() for t in tests]}

@router.get("/curriculum/{scout_name}")
def get_curriculum(scout_name: str):
    progress = academy_curriculum.get_all_for_scout(scout_name)
    return {"curriculum": [p.model_dump() for p in progress]}
