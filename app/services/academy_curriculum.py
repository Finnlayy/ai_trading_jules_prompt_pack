import json
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from app.schemas.academy import CurriculumProgress

DATA_DIR = Path("data")
CURRICULUM_FILE = DATA_DIR / "curriculum_progress.json"

class AcademyCurriculumService:
    def __init__(self):
        self._progress: Dict[str, CurriculumProgress] = {}
        self._ensure_files()
        self.load_progress()

    def _ensure_files(self):
        if not CURRICULUM_FILE.exists():
            with open(CURRICULUM_FILE, "w") as f:
                json.dump([], f)

    def load_progress(self):
        if CURRICULUM_FILE.exists():
            try:
                with open(CURRICULUM_FILE, "r") as f:
                    data = json.load(f)
                    for item in data:
                        cp = CurriculumProgress(**item)
                        # Composite key: scout_name + level
                        key = f"{cp.scout_name}_{cp.curriculum_level}"
                        self._progress[key] = cp
            except Exception as e:
                print(f"Error loading curriculum progress: {e}")

    def save_progress(self):
        try:
            with open(CURRICULUM_FILE, "w") as f:
                json.dump([cp.model_dump() for cp in self._progress.values()], f, indent=2)
        except Exception as e:
            print(f"Error saving curriculum progress: {e}")

    def get_progress(self, scout_name: str, level: str = "Beginner") -> CurriculumProgress:
        key = f"{scout_name}_{level}"
        if key not in self._progress:
            req_drills = {"Beginner": 10, "Intermediate": 25, "Advanced": 50, "Master": 100}.get(level, 10)
            cp = CurriculumProgress(
                scout_name=scout_name,
                curriculum_level=level,
                required_drills=req_drills
            )
            self._progress[key] = cp
            self.save_progress()
        return self._progress[key]

    def record_drill_result(self, scout_name: str, level: str, is_correct: bool, confidence: float):
        cp = self.get_progress(scout_name, level)
        cp.completed_drills += 1
        if is_correct:
            cp.passed_drills += 1

        # Cumulative moving average for confidence
        cp.average_confidence = cp.average_confidence + ((confidence - cp.average_confidence) / cp.completed_drills)
        self.save_progress()

    def get_all_for_scout(self, scout_name: str) -> List[CurriculumProgress]:
        return [cp for cp in self._progress.values() if cp.scout_name == scout_name]

academy_curriculum = AcademyCurriculumService()
