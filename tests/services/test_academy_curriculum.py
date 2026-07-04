import pytest
import json
from pathlib import Path
from app.services.academy_curriculum import AcademyCurriculumService
from app.schemas.academy import CurriculumProgress

@pytest.fixture
def mock_curriculum_file(tmp_path, monkeypatch):
    test_file = tmp_path / "test_curriculum.json"
    monkeypatch.setattr("app.services.academy_curriculum.CURRICULUM_FILE", test_file)
    return test_file

def test_init_creates_file(mock_curriculum_file):
    assert not mock_curriculum_file.exists()
    service = AcademyCurriculumService()
    assert mock_curriculum_file.exists()
    with open(mock_curriculum_file, "r") as f:
        data = json.load(f)
    assert data == []

def test_get_progress_new_scout(mock_curriculum_file):
    service = AcademyCurriculumService()

    # Test getting progress for a new scout
    progress = service.get_progress("ScoutA", "Intermediate")

    assert progress.scout_name == "ScoutA"
    assert progress.curriculum_level == "Intermediate"
    assert progress.required_drills == 25
    assert progress.completed_drills == 0
    assert progress.passed_drills == 0
    assert progress.average_confidence == 0.0

    # Verify it was added to the internal dictionary
    assert "ScoutA_Intermediate" in service._progress

    # Verify it was saved to the file
    with open(mock_curriculum_file, "r") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["scout_name"] == "ScoutA"
    assert data[0]["curriculum_level"] == "Intermediate"

def test_record_drill_result(mock_curriculum_file):
    service = AcademyCurriculumService()

    # Record first drill (correct)
    service.record_drill_result("ScoutB", "Beginner", is_correct=True, confidence=0.8)

    progress = service.get_progress("ScoutB", "Beginner")
    assert progress.completed_drills == 1
    assert progress.passed_drills == 1
    assert progress.average_confidence == 0.8

    # Record second drill (incorrect)
    service.record_drill_result("ScoutB", "Beginner", is_correct=False, confidence=0.4)

    progress = service.get_progress("ScoutB", "Beginner")
    assert progress.completed_drills == 2
    assert progress.passed_drills == 1
    # average_confidence = 0.8 + ((0.4 - 0.8) / 2) = 0.8 - 0.2 = 0.6
    assert progress.average_confidence == pytest.approx(0.6)

    # Record third drill (correct)
    service.record_drill_result("ScoutB", "Beginner", is_correct=True, confidence=0.9)
    progress = service.get_progress("ScoutB", "Beginner")
    assert progress.completed_drills == 3
    assert progress.passed_drills == 2
    # average_confidence = 0.6 + ((0.9 - 0.6) / 3) = 0.6 + 0.1 = 0.7
    assert progress.average_confidence == pytest.approx(0.7)

def test_get_all_for_scout(mock_curriculum_file):
    service = AcademyCurriculumService()

    # Add multiple levels for ScoutC and one for ScoutD
    service.get_progress("ScoutC", "Beginner")
    service.get_progress("ScoutC", "Intermediate")
    service.get_progress("ScoutD", "Beginner")

    scout_c_progress = service.get_all_for_scout("ScoutC")

    assert len(scout_c_progress) == 2
    levels = [p.curriculum_level for p in scout_c_progress]
    assert "Beginner" in levels
    assert "Intermediate" in levels

    scout_d_progress = service.get_all_for_scout("ScoutD")
    assert len(scout_d_progress) == 1
    assert scout_d_progress[0].curriculum_level == "Beginner"

def test_load_existing_progress(mock_curriculum_file):
    # Setup initial data
    initial_data = [
        {
            "scout_name": "ScoutE",
            "curriculum_level": "Advanced",
            "completed_drills": 10,
            "required_drills": 50,
            "passed_drills": 8,
            "average_confidence": 0.75
        }
    ]
    with open(mock_curriculum_file, "w") as f:
        json.dump(initial_data, f)

    # Initializing service should load the existing data
    service = AcademyCurriculumService()

    assert "ScoutE_Advanced" in service._progress
    progress = service._progress["ScoutE_Advanced"]
    assert progress.scout_name == "ScoutE"
    assert progress.completed_drills == 10
    assert progress.passed_drills == 8
    assert progress.average_confidence == 0.75

def test_save_progress_error(mock_curriculum_file, capsys, monkeypatch):
    service = AcademyCurriculumService()
    service.get_progress("ScoutF", "Beginner") # This triggers a save

    # Create an un-openable directory with the file name to trigger an error
    mock_curriculum_file.unlink() # remove the file
    mock_curriculum_file.mkdir() # replace with a dir, open() will fail

    # Trigger a save
    service.save_progress()

    # Check that it didn't crash and printed an error message
    captured = capsys.readouterr()
    assert "Error saving curriculum progress" in captured.out

def test_load_progress_error(mock_curriculum_file, capsys):
    # Write invalid JSON to trigger an error on load
    with open(mock_curriculum_file, "w") as f:
        f.write("Not valid JSON")

    service = AcademyCurriculumService() # __init__ calls load_progress

    # Check that it didn't crash and printed an error message
    captured = capsys.readouterr()
    assert "Error loading curriculum progress" in captured.out
