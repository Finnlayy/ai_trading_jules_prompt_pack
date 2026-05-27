import pytest
from app.services.ab_testing import ABTestingService

@pytest.fixture
def ab_service(tmp_path):
    import app.services.ab_testing
    app.services.ab_testing.DATA_DIR = tmp_path
    app.services.ab_testing.AB_TESTS_FILE = tmp_path / "ab.json"
    return ABTestingService()

def test_ab_testing_lifecycle(ab_service):
    test = ab_service.start_test("technical", "v1_base", "v2_advanced")
    assert test.status == "running"

    # Record some calls
    ab_service.record_call(test.test_id, is_variant_a=True, is_correct=True)
    ab_service.record_call(test.test_id, is_variant_a=True, is_correct=False)

    ab_service.record_call(test.test_id, is_variant_a=False, is_correct=True)
    ab_service.record_call(test.test_id, is_variant_a=False, is_correct=True)

    concluded = ab_service.conclude_test(test.test_id)
    assert concluded.status == "concluded"
    assert concluded.calls_a == 2
    assert concluded.calls_b == 2
    # B had 2 correct vs A's 1 correct, so B should win
    assert concluded.winner_version == "v2_advanced"
