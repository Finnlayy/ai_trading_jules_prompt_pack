import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.services.training_loop import TrainingLoopService

@pytest.fixture
def training_loop():
    service = TrainingLoopService()
    # Ensure it's not actually started by default in tests
    service.is_running = False
    return service

@pytest.mark.asyncio
async def test_start_stop(training_loop):
    # Ensure enabled flag is bypassed if disabled in environment
    with patch("app.services.training_loop.TRAINING_LOOP_ENABLED", True):
        # We need to mock _loop_routine so it doesn't run forever
        with patch.object(training_loop, '_loop_routine', return_value=None):
            await training_loop.start()
            assert training_loop.is_running is True
            assert training_loop.task is not None

            await training_loop.stop()
            assert training_loop.is_running is False
            assert training_loop.task is None

@pytest.mark.asyncio
async def test_update_diversity(training_loop):
    # Test diversity update logic with 100% agreement
    training_loop._update_diversity(["PROCEED", "PROCEED", "PROCEED", "PROCEED"])
    assert training_loop.diversity_stats.agreement_rate == 1.0
    assert training_loop.diversity_stats.status == "echo_chamber"

    # Reset
    training_loop.diversity_stats.total_evaluations = 0

    # Test diversity update logic with mixed agreement (50% / 50%)
    training_loop._update_diversity(["PROCEED", "REJECT", "PROCEED", "REJECT"])
    assert training_loop.diversity_stats.agreement_rate == 0.5

    # With 0.5 agreement, status could be "divergent" based on code logic:
    # elif self.diversity_stats.agreement_rate < 0.5:
    # Actually, if agreement is exactly 0.5, status is "optimal" (<= 0.9 and >= 0.5).
    assert training_loop.diversity_stats.status == "optimal"

@pytest.mark.asyncio
async def test_trigger_manual_cycle(training_loop):
    # Test manual cycle triggers _run_cycle
    with patch.object(training_loop, '_run_cycle') as mock_run_cycle:
        await training_loop.trigger_manual_cycle()
        mock_run_cycle.assert_called_once()

@pytest.mark.asyncio
async def test_run_cycle_full(training_loop):
    # Test _run_cycle directly to ensure no exceptions are raised
    # and all the mocked services are called.

    with patch("app.services.training_loop.training_drills.generate_random_drill") as mock_gen_drill, \
         patch("app.services.training_loop.agent_registry.get_identity") as mock_get_ident, \
         patch("app.services.training_loop.training_drills.evaluate_drill") as mock_eval_drill, \
         patch("app.services.training_loop.academy_curriculum.record_drill_result") as mock_record_drill, \
         patch("app.services.training_loop.agent_registry.save_registry") as mock_save_reg, \
         patch("app.services.training_loop.prompt_evolution.create_version") as mock_create_version, \
         patch("app.services.training_loop.ab_testing.start_test") as mock_ab_test:

        # Setup mocks
        mock_drill = MagicMock()
        mock_drill.expected_outcome = "PROCEED"
        mock_gen_drill.return_value = mock_drill

        mock_ident = MagicMock()
        mock_ident.accuracy = 0.5
        mock_ident.total_calls = 0
        mock_get_ident.return_value = mock_ident

        mock_eval_result = MagicMock()
        mock_eval_result.is_correct = True
        mock_eval_result.confidence = 0.8
        mock_eval_result.model_dump.return_value = {"mock": "data"}
        mock_eval_drill.return_value = mock_eval_result

        # Run cycle
        await training_loop._run_cycle()

        # Check asserts
        assert mock_gen_drill.call_count == 6  # 6 scouts
        assert mock_eval_drill.call_count == 6
        assert mock_record_drill.call_count == 6

        assert len(training_loop.recent_drills) == 6
        assert training_loop.last_run_time is not None

@pytest.mark.asyncio
async def test_check_auto_evolution(training_loop):
    # Test auto evolution logic when conditions are met

    with patch("app.services.training_loop.agent_registry.get_identity") as mock_get_ident, \
         patch("app.services.training_loop.random.random", return_value=0.01), \
         patch("app.services.training_loop.prompt_evolution.create_version") as mock_create_version, \
         patch("app.services.training_loop.ab_testing.start_test") as mock_ab_test, \
         patch("app.services.training_loop.agent_registry.save_registry") as mock_save_reg:

        # Case 1: Conditions met (total_calls > 20, accuracy < 0.6, random < 0.05)
        mock_ident = MagicMock()
        mock_ident.total_calls = 25
        mock_ident.accuracy = 0.5
        mock_ident.generation = 1
        mock_ident.born_from = "v1"
        mock_get_ident.return_value = mock_ident

        await training_loop._check_auto_evolution("technical")

        mock_create_version.assert_called_once_with(
            "technical",
            "v2_auto_evolved",
            "Auto-evolved prompt for technical focusing on recent failures.",
            parent_version="v1",
            change_summary="Auto-correction from Training Loop"
        )
        mock_ab_test.assert_called_once_with("technical", "v1", "v2_auto_evolved")
        assert mock_ident.generation == 2
        mock_save_reg.assert_called_once()

@pytest.mark.asyncio
async def test_check_auto_evolution_no_trigger(training_loop):
    # Test auto evolution logic when conditions are NOT met

    with patch("app.services.training_loop.agent_registry.get_identity") as mock_get_ident, \
         patch("app.services.training_loop.random.random", return_value=0.1), \
         patch("app.services.training_loop.prompt_evolution.create_version") as mock_create_version, \
         patch("app.services.training_loop.ab_testing.start_test") as mock_ab_test, \
         patch("app.services.training_loop.agent_registry.save_registry") as mock_save_reg:

        # Conditions NOT met (random > 0.05)
        mock_ident = MagicMock()
        mock_ident.total_calls = 25
        mock_ident.accuracy = 0.5
        mock_get_ident.return_value = mock_ident

        await training_loop._check_auto_evolution("technical")

        mock_create_version.assert_not_called()
        mock_ab_test.assert_not_called()
        mock_save_reg.assert_not_called()

def test_get_status(training_loop):
    status = training_loop.get_status()
    assert "is_running" in status
    assert "is_night_time" in status
    assert "last_run_time" in status
    assert "recent_drills" in status
    assert "diversity" in status
