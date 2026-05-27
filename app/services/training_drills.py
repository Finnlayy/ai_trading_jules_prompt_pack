import uuid
import random
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from pathlib import Path
DRILL_RESULTS_FILE = Path('data/drill_results.jsonl')
from app.schemas.academy import SyntheticDrill, DrillResult, CareerEntry
from app.services.agent_registry import agent_registry


class TrainingDrillsService:
    def __init__(self):
        pass

    def generate_random_drill(self, scout_name: str, difficulty: int = 1) -> SyntheticDrill:
        drill_types = {
            "technical": "pattern_recognition",
            "sentiment": "sentiment_analysis",
            "risk": "crisis_detection",
            "macro": "regime_identification"
        }

        drill_type = drill_types.get(scout_name, "pattern_recognition")

        scenario_data = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "mock_price": 60000 + random.randint(-1000, 1000),
            "context": f"Simulated {drill_type} scenario for difficulty {difficulty}"
        }

        expected_outcome = random.choice(["PROCEED", "REJECT"])

        if drill_type == "crisis_detection":
            scenario_data["crisis_score"] = 80 if expected_outcome == "REJECT" else 20
        elif drill_type == "pattern_recognition":
            scenario_data["confluence_score"] = 90 if expected_outcome == "PROCEED" else 40
        elif drill_type == "sentiment_analysis":
            scenario_data["headline"] = "Market dumps as regulations tighten" if expected_outcome == "REJECT" else "ETF Approved, institutional inflows rise"

        return SyntheticDrill(
            drill_type=drill_type,
            scout_target=scout_name,
            scenario_data=scenario_data,
            expected_outcome=expected_outcome,
            difficulty=difficulty
        )

    def generate_drills(self, scout_name: str, count: int = 5) -> List[SyntheticDrill]:
        return [self.generate_random_drill(scout_name, difficulty=random.randint(1, 3)) for _ in range(count)]

    async def evaluate_drill(self, drill: SyntheticDrill, scout_decision: str, confidence: float) -> DrillResult:
        # A simple string comparison for the MVP
        is_correct = (scout_decision.upper() == drill.expected_outcome.upper())

        result = DrillResult(
            drill_id=drill.drill_id,
            scout_name=drill.scout_target,
            scout_decision=scout_decision,
            is_correct=is_correct,
            confidence=confidence,
            feedback_notes=f"Expected {drill.expected_outcome}, got {scout_decision}."
        )


        # Log to agent registry
        career_entry = CareerEntry(
            scout_name=drill.scout_target,
            event_type="prediction_result",
            details={
                "symbol": drill.scenario_data.get("symbol", "UNKNOWN"),
                "is_correct": is_correct,
                "drill_type": drill.drill_type,
                "drill_id": drill.drill_id
            }
        )
        await agent_registry.log_career_event(career_entry)

        # Log specific drill result
        def _write_drill():
            with open(DRILL_RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(result.model_dump_json() + "\n")

        await asyncio.to_thread(_write_drill)


        return result

training_drills = TrainingDrillsService()
