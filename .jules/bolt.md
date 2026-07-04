## 2024-07-25 - GlintBroker Missing Coverage Addressed
**Learning:** Pydantic's BaseModel strictness prevents dynamic attribute assignment when testing properties like size_usdt. Using `object.__setattr__(payload, 'size_usdt', 100.0)` bypasses Pydantic validations, allowing tests to correctly construct mocks.
**Action:** Use `object.__setattr__` when mutating Pydantic BaseModel attributes inside isolated tests to overcome restricted configurations (like frozen or arbitrary field validation) instead of hacking the model config directly.
