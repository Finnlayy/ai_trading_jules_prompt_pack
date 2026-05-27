import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
from app.schemas.academy import PromptVersion

DATA_DIR = Path("data")
PROMPT_REGISTRY_FILE = DATA_DIR / "prompt_registry.json"

class PromptEvolutionService:
    def __init__(self):
        self._versions: Dict[str, PromptVersion] = {}
        self._ensure_files()
        self.load_registry()

    def _ensure_files(self):
        if not PROMPT_REGISTRY_FILE.exists():
            PROMPT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PROMPT_REGISTRY_FILE, "w") as f:
                json.dump([], f)

    def load_registry(self):
        if PROMPT_REGISTRY_FILE.exists():
            try:
                with open(PROMPT_REGISTRY_FILE, "r") as f:
                    data = json.load(f)
                    for item in data:
                        pv = PromptVersion(**item)
                        self._versions[pv.version_id] = pv
            except Exception as e:
                print(f"Error loading prompt registry: {e}")

        # Populate defaults if empty
        if not self._versions:
            for scout in ["technical", "sentiment", "risk", "macro", "execution", "correlation"]:
                self.create_version(scout, "v1_base", f"You are the {scout} scout...", change_summary="Base version")

    def save_registry(self):
        try:
            with open(PROMPT_REGISTRY_FILE, "w") as f:
                json.dump([v.model_dump() for v in self._versions.values()], f, indent=2)
        except Exception as e:
            print(f"Error saving prompt registry: {e}")

    def create_version(self, scout_name: str, version_id: str, prompt_text: str, parent_version: Optional[str] = None, change_summary: str = "") -> PromptVersion:
        pv = PromptVersion(
            version_id=version_id,
            scout_name=scout_name,
            prompt_text=prompt_text,
            parent_version=parent_version,
            change_summary=change_summary
        )
        self._versions[version_id] = pv
        self.save_registry()
        return pv

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        return self._versions.get(version_id)

    def get_all_for_scout(self, scout_name: str) -> List[PromptVersion]:
        versions = [v for v in self._versions.values() if v.scout_name == scout_name]
        versions.sort(key=lambda x: x.created_at, reverse=True)
        return versions

prompt_evolution = PromptEvolutionService()
