import re

filepath = 'app/services/paper_training_pipeline.py'
with open(filepath, 'r') as f:
    content = f.read()

old_init = """    def __init__(
        self,
        ai_review_layer: Any = None,
        risk_engine: Any = None,
        paper_broker: Any = None,
        recorder: Any = None,
    ) -> None:
        self.ai_review_layer = ai_review_layer or ai_review_instance
        self.risk_engine = risk_engine or risk_engine_instance
        self.paper_broker = paper_broker or KrakenPaperBroker()
        self.recorder = recorder or lifecycle_recorder"""

new_init = """    def __init__(
        self,
        ai_review_layer: Any = None,
        risk_engine: Any = None,
        paper_broker: Any = None,
        recorder: Any = None,
    ) -> None:
        self.ai_review_layer = ai_review_layer or ai_review_instance
        self.risk_engine = risk_engine or risk_engine_instance
        self.paper_broker = paper_broker
        self.recorder = recorder or lifecycle_recorder"""

content = content.replace(old_init, new_init)

old_start = """    async def process_candidate(self, payload: M8Payload) -> dict[str, Any]:"""

new_start = """    async def process_candidate(self, payload: M8Payload) -> dict[str, Any]:
        if self.paper_broker is None:
            self.paper_broker = KrakenPaperBroker()"""

content = content.replace(old_start, new_start)

with open(filepath, 'w') as f:
    f.write(content)
