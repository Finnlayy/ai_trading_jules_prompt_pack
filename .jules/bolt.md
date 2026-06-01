## 2024-05-20 - Testing Gap in Broker Interface
**Learning:** Added base testing suite for `BaseBroker` using a concrete dummy class `DummyBroker` to enforce abstract base implementation properties and check properties like typing signatures properly under `pytest`.
**Action:** Always maintain minimal dummy classes when writing integration tests for core python base interfaces.
