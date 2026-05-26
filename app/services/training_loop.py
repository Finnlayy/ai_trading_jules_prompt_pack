import asyncio
import os
import random
from datetime import datetime
from typing import Dict, Any, List

from app.schemas.academy import DiversityMonitorStats
from app.services.training_drills import training_drills
from app.services.academy_curriculum import academy_curriculum
from app.services.agent_registry import agent_registry
from app.services.prompt_evolution import prompt_evolution
from app.services.ab_testing import ab_testing

# Configuration
TRAINING_LOOP_ENABLED = os.getenv("TRAINING_LOOP_ENABLED", "true").lower() == "true"
TRAINING_LOOP_NIGHT_MODE = os.getenv("TRAINING_LOOP_NIGHT_MODE", "true").lower() == "true"

class TrainingLoopService:
    def __init__(self):
        self.is_running = False
        self.task = None
        self.diversity_stats = DiversityMonitorStats()
        self.last_run_time = None
        self.recent_drills = []

    def _is_night_time(self) -> bool:
        if not TRAINING_LOOP_NIGHT_MODE:
            return True
        hour = datetime.utcnow().hour
        # Default 22:00 to 06:00
        return hour >= 22 or hour < 6

    async def start(self):
        if not TRAINING_LOOP_ENABLED:
            return
        if self.is_running:
            return

        self.is_running = True
        self.task = asyncio.create_task(self._loop_routine())

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            self.task = None

    async def trigger_manual_cycle(self):
        await self._run_cycle()

    async def _loop_routine(self):
        while self.is_running:
            if self._is_night_time():
                await self._run_cycle()

            # Sleep between drills to respect rate limits (simulated per hour limit)
            # Default 12 drills per hour = 1 drill every 5 minutes
            await asyncio.sleep(300)

    async def _run_cycle(self):
        self.last_run_time = datetime.utcnow().isoformat()
        scouts = ["technical", "sentiment", "risk", "macro"]

        # Track agreements for diversity monitor
        decisions = []

        for scout in scouts:
            # 1. Generate Drill
            drill = training_drills.generate_random_drill(scout, difficulty=random.randint(1, 3))

            # 2. Simulate AI decision (for MVP, we use simple random/weighted logic instead of full LLM call)
            # In a real impl, we would call `ai_kimi.py` or similar
            # We mock it based on their accuracy to keep it somewhat realistic
            identity = agent_registry.get_identity(scout)
            acc = identity.accuracy if identity and identity.accuracy > 0 else 0.5

            # Simulated decision
            if random.random() < acc:
                scout_decision = drill.expected_outcome
            else:
                scout_decision = "PROCEED" if drill.expected_outcome == "REJECT" else "REJECT"

            decisions.append(scout_decision)

            # 3. Evaluate Drill
            result = await training_drills.evaluate_drill(drill, scout_decision, confidence=random.uniform(0.5, 0.99))

            # Update curriculum
            academy_curriculum.record_drill_result(scout, "Beginner", result.is_correct, result.confidence)

            # 4. Check for Auto-Prompt-Evolution
            await self._check_auto_evolution(scout)

            # Save for UI log
            self.recent_drills.insert(0, result.model_dump())
            if len(self.recent_drills) > 50:
                self.recent_drills.pop()

        # 5. Update Diversity Monitor
        self._update_diversity(decisions)

    async def _check_auto_evolution(self, scout_name: str):
        # Trigger evolution if the scout has a bad streak (simulated using registry data)
        ident = agent_registry.get_identity(scout_name)
        if not ident: return

        # In MVP, if the scout just dropped accuracy significantly or hit an artificial trigger
        # We'll simulate a 5% chance of triggering evolution if they have > 20 calls and accuracy < 60%
        if ident.total_calls > 20 and ident.accuracy < 0.6 and random.random() < 0.05:
            # Generate new prompt
            new_version_id = f"v{ident.generation + 1}_auto_evolved"
            prompt_evolution.create_version(
                scout_name,
                new_version_id,
                f"Auto-evolved prompt for {scout_name} focusing on recent failures.",
                parent_version=ident.born_from,
                change_summary="Auto-correction from Training Loop"
            )

            # Start A/B test
            ab_testing.start_test(scout_name, ident.born_from, new_version_id)

            ident.generation += 1
            agent_registry.save_registry()

    def _update_diversity(self, decisions: List[str]):
        if not decisions: return

        proceeds = decisions.count("PROCEED")
        rejects = decisions.count("REJECT")

        # Agreement rate: max percentage of one decision
        agreement = max(proceeds, rejects) / len(decisions)

        # Update exponential moving average of agreement rate
        if self.diversity_stats.total_evaluations == 0:
            self.diversity_stats.agreement_rate = agreement
        else:
            self.diversity_stats.agreement_rate = (self.diversity_stats.agreement_rate * 0.9) + (agreement * 0.1)

        self.diversity_stats.total_evaluations += 1

        if self.diversity_stats.agreement_rate > 0.9:
            self.diversity_stats.high_agreement_warnings += 1
            self.diversity_stats.status = "echo_chamber"
        elif self.diversity_stats.agreement_rate < 0.5:
            self.diversity_stats.low_agreement_warnings += 1
            self.diversity_stats.status = "divergent"
        else:
            self.diversity_stats.status = "optimal"

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "is_night_time": self._is_night_time(),
            "last_run_time": self.last_run_time,
            "recent_drills": self.recent_drills,
            "diversity": self.diversity_stats.model_dump()
        }

training_loop = TrainingLoopService()
