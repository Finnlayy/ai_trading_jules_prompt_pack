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
