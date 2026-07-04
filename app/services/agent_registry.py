from app.core.utils import write_json_async
import json
import asyncio
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from app.schemas.academy import ScoutIdentity, CareerEntry, Badge
from app.services.ai.gem_agents import DEFAULT_AGENT_DEFINITIONS

DATA_DIR = Path("data")
CAREER_LOG_FILE = DATA_DIR / "agent_careers.jsonl"
REGISTRY_FILE = DATA_DIR / "agent_registry.json"

SCOUT_DEFAULTS = [
    {
        "name": "macro_sentinel",
        "archetype": "Stratege",
        "personality_vector": {"analytical": 0.7, "cautious": 0.7, "momentum_driven": 0.3}
    },
    {
        "name": "market_dna",
        "archetype": "Analyst",
        "personality_vector": {"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.8}
    },
    {
        "name": "structural_architect",
        "archetype": "Architekt",
        "personality_vector": {"analytical": 0.8, "cautious": 0.6, "momentum_driven": 0.2}
    },
    {
        "name": "harmony_coordinator",
        "archetype": "Diplomat",
        "personality_vector": {"analytical": 0.5, "cautious": 0.5, "momentum_driven": 0.5}
    },
    {
        "name": "indicator_fusion",
        "archetype": "Analyst",
        "personality_vector": {"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.8}
    },
    {
        "name": "risk_kernel",
        "archetype": "Wächter",
        "personality_vector": {"analytical": 0.8, "cautious": 0.95, "momentum_driven": 0.1}
    },
    {
        "name": "pine_core",
        "archetype": "Entwickler",
        "personality_vector": {"analytical": 0.9, "cautious": 0.6, "momentum_driven": 0.3}
    },
    {
        "name": "payload_qa",
        "archetype": "Prüfer",
        "personality_vector": {"analytical": 0.9, "cautious": 0.9, "momentum_driven": 0.1}
    },
    {
        "name": "execution_watchdog",
        "archetype": "Operator",
        "personality_vector": {"analytical": 0.9, "cautious": 0.8, "momentum_driven": 0.2}
    },
    {
        "name": "evolution_optimizer",
        "archetype": "Forscher",
        "personality_vector": {"analytical": 0.8, "cautious": 0.4, "momentum_driven": 0.6}
    }
]

for definition in DEFAULT_AGENT_DEFINITIONS:
    if not any(item["name"] == definition.name for item in SCOUT_DEFAULTS):
        SCOUT_DEFAULTS.append(
            {
                "name": definition.name,
                "archetype": definition.archetype,
                "personality_vector": definition.personality_vector,
            }
        )

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

    def _next_deployed_name(self) -> str:
        index = len(self._identities) + 1
        while f"ui-agent-{index}" in self._identities:
            index += 1
        return f"ui-agent-{index}"

    def deploy_identity(
        self,
        name: str | None = None,
        archetype: str = "Analyst",
        personality_vector: Dict[str, float] | None = None,
        specialization_symbols: List[str] | None = None,
    ) -> ScoutIdentity:
        agent_name = (name or "").strip() or self._next_deployed_name()
        if agent_name in self._identities:
            raise ValueError(f"Agent {agent_name} already exists")

        identity = ScoutIdentity(
            name=agent_name,
            archetype=archetype,
            born_from="ui_deploy",
            specialization_symbols=specialization_symbols or [],
            personality_vector=personality_vector or {},
        )
        self._identities[identity.name] = identity
        self.save_registry()
        return identity

    async def log_career_event(
        self,
        entry: CareerEntry,
        *,
        save_registry: bool = True,
        write_log: bool = True,
    ):
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
                await self._check_badges(
                    ident,
                    entry,
                    save_registry=save_registry,
                    write_log=write_log,
                )

            elif entry.event_type == "badge_earned":
                badge_data = entry.details.get("badge", {})
                if badge_data:
                    badge = Badge(**badge_data)
                    ident.badges.append(badge)

            if save_registry:
                self.save_registry()
                try:
                    from app.services.wiki_service import update_second_brain
                    update_second_brain()
                except Exception:
                    pass

        if not write_log:
            return

        def _write_log():
            with open(CAREER_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")

        # Offload file write to thread
        await asyncio.to_thread(_write_log)

    async def _check_badges(
        self,
        ident: ScoutIdentity,
        entry: CareerEntry,
        *,
        save_registry: bool = True,
        write_log: bool = True,
    ):
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
            await self.log_career_event(
                badge_entry,
                save_registry=save_registry,
                write_log=write_log,
            )

    def get_career_log(self, scout_name: str) -> List[CareerEntry]:
        entries = []
        if not CAREER_LOG_FILE.exists():
            return entries

        try:
            with open(CAREER_LOG_FILE, "r") as f:
                for line in f:
                    if line.strip():
                        # ⚡ Bolt Optimization: Fast string match to skip JSON parsing for irrelevant lines
                        if f'"scout_name":"{scout_name}"' not in line and f'"scout_name": "{scout_name}"' not in line:
                            continue
                        data = json.loads(line)
                        if data.get("scout_name") == scout_name:
                            entries.append(CareerEntry(**data))
        except Exception as e:
            print(f"Error reading career log: {e}")
        return entries

    def get_recent_career_events(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
    ) -> List[CareerEntry]:
        entries: List[CareerEntry] = []
        if not CAREER_LOG_FILE.exists():
            return entries

        try:
            with open(CAREER_LOG_FILE, "r", encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
            for line in reversed(lines):
                # ⚡ Bolt Optimization: Fast string match to skip JSON parsing for irrelevant lines
                if event_type and f'"event_type":"{event_type}"' not in line and f'"event_type": "{event_type}"' not in line:
                    continue
                data = json.loads(line)
                if event_type and data.get("event_type") != event_type:
                    continue
                entries.append(CareerEntry(**data))
                if len(entries) >= limit:
                    break
        except Exception as e:
            print(f"Error reading recent career events: {e}")
        return entries

agent_registry = AgentRegistryService()
