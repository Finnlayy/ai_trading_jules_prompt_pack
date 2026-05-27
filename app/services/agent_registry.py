import json
import os
import asyncio
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from app.schemas.academy import ScoutIdentity, CareerEntry, Badge, AgentLeaderboardEntry

DATA_DIR = Path("data")
CAREER_LOG_FILE = DATA_DIR / "agent_careers.jsonl"
REGISTRY_FILE = DATA_DIR / "agent_registry.json"

SCOUT_DEFAULTS = [
    {
        "name": "technical",
        "archetype": "Analyst",
        "personality_vector": {"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.8}
    },
    {
        "name": "sentiment",
        "archetype": "Diplomat",
        "personality_vector": {"analytical": 0.3, "cautious": 0.5, "momentum_driven": 0.9}
    },
    {
        "name": "risk",
        "archetype": "Wächter",
        "personality_vector": {"analytical": 0.8, "cautious": 0.95, "momentum_driven": 0.1}
    },
    {
        "name": "macro",
        "archetype": "Stratege",
        "personality_vector": {"analytical": 0.7, "cautious": 0.7, "momentum_driven": 0.5}
    },
    {
        "name": "execution",
        "archetype": "Operateur",
        "personality_vector": {"analytical": 0.9, "cautious": 0.8, "momentum_driven": 0.2}
    },
    {
        "name": "correlation",
        "archetype": "Architekt",
        "personality_vector": {"analytical": 0.85, "cautious": 0.85, "momentum_driven": 0.1}
    }
]

class AgentRegistryService:
    def __init__(self):
        self._identities: Dict[str, ScoutIdentity] = {}
        self._ensure_files()
        self.load_registry()

    def _ensure_files(self):
        DATA_DIR.mkdir(exist_ok=True)
        if not CAREER_LOG_FILE.exists():
            CAREER_LOG_FILE.touch()

    def load_registry(self):
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, "r") as f:
                    data = json.load(f)
                    for scout_data in data:
                        identity = ScoutIdentity(**scout_data)
                        self._identities[identity.name] = identity
            except Exception as e:
                print(f"Error loading agent registry: {e}")

        # Ensure default scouts exist
        for default in SCOUT_DEFAULTS:
            if default["name"] not in self._identities:
                new_identity = ScoutIdentity(
                    name=default["name"],
                    archetype=default["archetype"],
                    personality_vector=default["personality_vector"]
                )
                self._identities[default["name"]] = new_identity
        self.save_registry()

    def save_registry(self):
        try:
            with open(REGISTRY_FILE, "w") as f:
                json.dump([i.model_dump() for i in self._identities.values()], f, indent=2)
        except Exception as e:
            print(f"Error saving agent registry: {e}")

    def get_identity(self, name: str) -> Optional[ScoutIdentity]:
        return self._identities.get(name)

    def get_all_identities(self) -> List[ScoutIdentity]:
        return list(self._identities.values())

    async def log_career_event(self, entry: CareerEntry):
        # Update identity stats if applicable
        ident = self._identities.get(entry.scout_name)
        if ident:
            if entry.event_type == "prediction_result":
                ident.total_calls += 1
                is_correct = entry.details.get("is_correct", False)
                if is_correct:
                    ident.correct_calls += 1
                    ident.current_streak += 1
                else:
                    ident.current_streak = 0

                ident.accuracy = ident.correct_calls / ident.total_calls if ident.total_calls > 0 else 0.0

                # Check for new badges
                await self._check_badges(ident, entry)

            elif entry.event_type == "badge_earned":
                badge_data = entry.details.get("badge", {})
                if badge_data:
                    badge = Badge(**badge_data)
                    ident.badges.append(badge)

            # Save the updated stats synchronously for now (MVP)
            self.save_registry()

        def _write_log():
            with open(CAREER_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")

        # Offload file write to thread
        await asyncio.to_thread(_write_log)

    async def _check_badges(self, ident: ScoutIdentity, entry: CareerEntry):
        # Evaluate badges based on current stats
        existing_badge_names = {b.name for b in ident.badges}
        new_badges = []

        if ident.total_calls >= 10 and "Apprentice" not in existing_badge_names:
            new_badges.append(Badge(name="Apprentice", description="10+ Calls", icon="🥉"))
        if ident.total_calls >= 50 and ident.accuracy >= 0.6 and "Adept" not in existing_badge_names:
            new_badges.append(Badge(name="Adept", description="50+ Calls, 60%+ Accuracy", icon="🥈"))
        if ident.total_calls >= 100 and ident.accuracy >= 0.7 and "Expert" not in existing_badge_names:
            new_badges.append(Badge(name="Expert", description="100+ Calls, 70%+ Accuracy", icon="🥇"))
        if ident.total_calls >= 500 and ident.accuracy >= 0.75 and "Master" not in existing_badge_names:
            new_badges.append(Badge(name="Master", description="500+ Calls, 75%+ Accuracy", icon="💎"))

        if ident.current_streak >= 10 and "Streak" not in existing_badge_names:
            new_badges.append(Badge(name="Streak", description="10 correct calls in a row", icon="⚡"))

        for badge in new_badges:
            badge_entry = CareerEntry(
                scout_name=ident.name,
                event_type="badge_earned",
                details={"badge": badge.model_dump()}
            )
            await self.log_career_event(badge_entry)

    def get_career_log(self, scout_name: str) -> List[CareerEntry]:
        entries = []
        if not CAREER_LOG_FILE.exists():
            return entries

        try:
            with open(CAREER_LOG_FILE, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        if data.get("scout_name") == scout_name:
                            entries.append(CareerEntry(**data))
        except Exception as e:
            print(f"Error reading career log: {e}")
        return entries

agent_registry = AgentRegistryService()
