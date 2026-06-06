from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.agent_registry import agent_registry
from typing import List, Dict, Any
import json

router = APIRouter(prefix="/academy", tags=["Academy"])


class AgentDeployRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    archetype: str = Field(default="Analyst", min_length=1, max_length=64)
    personality_vector: Dict[str, float] = Field(default_factory=dict)
    specialization_symbols: List[str] = Field(default_factory=list)

@router.get("/agents/registry")
def get_agents_registry():
    agents = agent_registry.get_all_identities()
    return {"agents": [a.model_dump() for a in agents]}


@router.post("/agents/deploy")
def deploy_agent(req: AgentDeployRequest | None = None):
    req = req or AgentDeployRequest()
    try:
        agent = agent_registry.deploy_identity(
            name=req.name,
            archetype=req.archetype,
            personality_vector=req.personality_vector,
            specialization_symbols=req.specialization_symbols,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return {"status": "created", "agent": agent.model_dump()}

@router.get("/agents/{scout_id}/career")
def get_agent_career(scout_id: str):
    # Using scout_id as scout_name for now since that's what's tracked mostly
    entries = agent_registry.get_career_log(scout_id)
    return {"career": [e.model_dump() for e in entries]}

@router.get("/agents/careers/recent")
def get_recent_agent_careers(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None),
):
    entries = agent_registry.get_recent_career_events(limit=limit, event_type=event_type)
    return {"career": [e.model_dump() for e in entries], "count": len(entries)}

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
from app.schemas.academy import AcademyPolicyPreviewRequest, SyntheticDrill
from app.services.academy_policy import academy_policy_service
from app.services.academy_policy.logging import ACTION_LOG_FILE

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

from app.services.training_loop import training_loop

@router.get("/status")
def get_academy_status():
    return training_loop.get_status()


@router.get("/policy/status")
def get_academy_policy_status():
    return academy_policy_service.get_status().model_dump()


@router.post("/policy/preview")
def preview_academy_policy(req: AcademyPolicyPreviewRequest | None = None):
    return academy_policy_service.preview(req or AcademyPolicyPreviewRequest())


@router.get("/policy/actions/recent")
def get_recent_policy_actions(limit: int = Query(default=50, ge=1, le=500)):
    if not ACTION_LOG_FILE.exists():
        return {"actions": [], "count": 0}

    actions = []
    try:
        with ACTION_LOG_FILE.open("r", encoding="utf-8") as handle:
            lines = [line for line in handle if line.strip()]
        for line in reversed(lines):
            actions.append(json.loads(line))
            if len(actions) >= limit:
                break
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read academy policy actions: {exc}")

    return {"actions": actions, "count": len(actions)}

@router.post("/train/start")
async def start_training():
    result = await training_loop.start()
    return {"status": "started" if result.get("started") else "not_started", **result}

@router.post("/train/stop")
async def stop_training():
    await training_loop.stop()
    return {"status": "stopped"}

@router.post("/drill/start")
async def trigger_manual_drill():
    await training_loop.trigger_manual_cycle()
    return {"status": "drill_cycle_completed"}
