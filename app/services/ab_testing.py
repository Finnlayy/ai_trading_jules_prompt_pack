import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timezone
from app.schemas.academy import ABTest

DATA_DIR = Path("data")
AB_TESTS_FILE = DATA_DIR / "ab_tests.json"

class ABTestingService:
    def __init__(self):
        self._tests: Dict[str, ABTest] = {}
        self._ensure_files()
        self.load_tests()

    def _ensure_files(self):
        if not AB_TESTS_FILE.exists():
            with open(AB_TESTS_FILE, "w") as f:
                json.dump([], f)

    def load_tests(self):
        if AB_TESTS_FILE.exists():
            try:
                with open(AB_TESTS_FILE, "r") as f:
                    data = json.load(f)
                    for item in data:
                        t = ABTest(**item)
                        self._tests[t.test_id] = t
            except Exception as e:
                print(f"Error loading AB tests: {e}")

    def save_tests(self):
        try:
            with open(AB_TESTS_FILE, "w") as f:
                json.dump([t.model_dump() for t in self._tests.values()], f, indent=2)
        except Exception as e:
            print(f"Error saving AB tests: {e}")

    def start_test(self, scout_name: str, variant_a: str, variant_b: str) -> ABTest:
        t = ABTest(
            scout_name=scout_name,
            variant_a_version=variant_a,
            variant_b_version=variant_b
        )
        self._tests[t.test_id] = t
        self.save_tests()
        return t

    def record_call(self, test_id: str, is_variant_a: bool, is_correct: bool):
        t = self._tests.get(test_id)
        if not t or t.status != "running":
            return

        if is_variant_a:
            t.calls_a += 1
            if is_correct: t.correct_a += 1
        else:
            t.calls_b += 1
            if is_correct: t.correct_b += 1

        self.save_tests()

    def conclude_test(self, test_id: str) -> Optional[ABTest]:
        t = self._tests.get(test_id)
        if not t:
            return None

        acc_a = t.correct_a / t.calls_a if t.calls_a > 0 else 0
        acc_b = t.correct_b / t.calls_b if t.calls_b > 0 else 0

        t.winner_version = t.variant_a_version if acc_a >= acc_b else t.variant_b_version
        t.status = "concluded"
        t.concluded_at = datetime.now(timezone.utc).isoformat()

        self.save_tests()
        return t

    def get_all(self) -> List[ABTest]:
        return list(self._tests.values())

ab_testing = ABTestingService()
