import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.training_loop import TrainingLoopService
from app.schemas.academy import SyntheticDrill, DrillResult

@pytest.fixture
def service():
    # Return a fresh instance of the service for each test
    return TrainingLoopService()

@pytest.mark.asyncio
async def test_training_loop_initial_status(service):
    """Test the initial status of the training loop."""
    status = service.get_status()
    assert status["is_running"] is False
    assert status["last_run_time"] is None
    assert status["recent_drills"] == []
    assert status["diversity"]["total_evaluations"] == 0

@pytest.mark.asyncio
async def test_update_diversity_no_decisions(service):
    """Test diversity update with empty decisions."""
    service._update_diversity([])
    assert service.diversity_stats.total_evaluations == 0

@pytest.mark.asyncio
async def test_update_diversity_with_decisions(service):
    """Test diversity update with valid decisions."""
    decisions = ["PROCEED", "REJECT", "PROCEED"]
    service._update_diversity(decisions)

    assert service.diversity_stats.total_evaluations == 1
    # max(2, 1) / 3 = 2/3 = 0.666...
    assert 0.66 < service.diversity_stats.agreement_rate < 0.67
    assert service.diversity_stats.status == "optimal"

@pytest.mark.asyncio
async def test_update_diversity_echo_chamber(service):
    """Test diversity monitor detects high agreement (echo chamber)."""
    decisions = ["PROCEED", "PROCEED", "PROCEED", "PROCEED"]

    # Needs multiple evaluations to build moving average if not first run
    # For first run, it takes the value directly
    service._update_diversity(decisions)

    assert service.diversity_stats.agreement_rate == 1.0
    assert service.diversity_stats.high_agreement_warnings == 1
    assert service.diversity_stats.status == "echo_chamber"

@pytest.mark.asyncio
async def test_update_diversity_divergent(service):
    """Test diversity monitor detects low agreement (divergent)."""
    # 2 PROCEED, 2 REJECT, agreement = 2/4 = 0.5.
    # Must be < 0.5 to trigger divergent.
    # Let's use 3 PROCEED, 3 REJECT, 1 OTHER
    decisions = ["PROCEED", "PROCEED", "REJECT", "REJECT", "OTHER"]

    service._update_diversity(decisions)

    assert service.diversity_stats.agreement_rate == 0.4
    assert service.diversity_stats.low_agreement_warnings == 1
    assert service.diversity_stats.status == "divergent"

@pytest.mark.asyncio
@patch('app.services.training_loop.training_drills')
@patch('app.services.training_loop.agent_registry')
@patch('app.services.training_loop.academy_curriculum')
async def test_run_cycle(mock_curriculum, mock_registry, mock_drills, service):
    """Test a full run cycle with mocked dependencies."""
    # Mocking drill generation
    mock_drill = SyntheticDrill(
        drill_type="pattern_recognition",
        scout_target="technical",
        scenario_data={},
        expected_outcome="PROCEED",
        difficulty=1
    )
    mock_drills.generate_random_drill.return_value = mock_drill

    # Mocking identity
    mock_identity = MagicMock()
    mock_identity.accuracy = 0.8
    mock_registry.get_identity.return_value = mock_identity

    # Mocking evaluation - must return a coroutine
    mock_result = DrillResult(
        drill_id=mock_drill.drill_id,
        scout_name="technical",
        scout_decision="PROCEED",
        is_correct=True,
        confidence=0.9
    )
    mock_drills.evaluate_drill = AsyncMock(return_value=mock_result)

    # Prevent _check_auto_evolution from doing anything complex
    with patch.object(service, '_check_auto_evolution') as mock_check_evo:
        mock_check_evo = AsyncMock()
        service._check_auto_evolution = mock_check_evo

        await service._run_cycle()

        # Verify calls
        assert mock_drills.generate_random_drill.call_count == 6 # 6 scouts
        assert mock_drills.evaluate_drill.call_count == 6
        assert mock_curriculum.record_drill_result.call_count == 6
        assert mock_check_evo.call_count == 6

        # Verify state updates
        assert service.last_run_time is not None
        assert len(service.recent_drills) == 6
        assert service.diversity_stats.total_evaluations == 1

@pytest.mark.asyncio
@patch('app.services.training_loop.agent_registry')
@patch('app.services.training_loop.prompt_evolution')
@patch('app.services.training_loop.ab_testing')
async def test_check_auto_evolution_triggers(mock_ab, mock_prompt_evo, mock_registry, service):
    """Test auto evolution triggers correctly."""
    mock_identity = MagicMock()
    mock_identity.total_calls = 25
    mock_identity.accuracy = 0.5
    mock_identity.generation = 1
    mock_identity.born_from = "v1"

    mock_registry.get_identity.return_value = mock_identity

    with patch('app.services.training_loop.random.random', return_value=0.01):
        await service._check_auto_evolution("technical")

        # Should trigger evolution
        assert mock_prompt_evo.create_version.call_count == 1
        assert mock_ab.start_test.call_count == 1
        assert mock_identity.generation == 2
        assert mock_registry.save_registry.call_count == 1

@pytest.mark.asyncio
@patch('app.services.training_loop.agent_registry')
@patch('app.services.training_loop.prompt_evolution')
@patch('app.services.training_loop.ab_testing')
async def test_check_auto_evolution_no_trigger_high_accuracy(mock_ab, mock_prompt_evo, mock_registry, service):
    """Test auto evolution does not trigger for high accuracy."""
    mock_identity = MagicMock()
    mock_identity.total_calls = 25
    mock_identity.accuracy = 0.8
    mock_registry.get_identity.return_value = mock_identity

    with patch('app.services.training_loop.random.random', return_value=0.01):
        await service._check_auto_evolution("technical")

        # Should NOT trigger evolution
        assert mock_prompt_evo.create_version.call_count == 0

@pytest.mark.asyncio
@patch('app.services.training_loop.asyncio.sleep', new_callable=AsyncMock)
async def test_start_stop(mock_sleep, service):
    """Test starting and stopping the training loop."""
    # Temporarily bypass the sleep to let one cycle run, then stop
    # But wait, it loops forever if is_running=True. We must stop it.

    with patch.object(service, '_run_cycle') as mock_run_cycle:
        mock_run_cycle = AsyncMock()
        service._run_cycle = mock_run_cycle

        # Override sleep to also stop the loop so it doesn't run forever
        async def stop_loop(*args):
            await service.stop()

        mock_sleep.side_effect = stop_loop

        await service.start()

        # Wait for task to finish, handle cancellation gracefully
        if service.task:
            try:
                await service.task
            except asyncio.CancelledError:
                pass

        assert not service.is_running
        assert mock_sleep.call_count >= 1

@pytest.mark.asyncio
async def test_trigger_manual_cycle(service):
    """Test manual cycle trigger."""
    with patch.object(service, '_run_cycle', new_callable=AsyncMock) as mock_run_cycle:
        await service.trigger_manual_cycle()
        assert mock_run_cycle.call_count == 1
