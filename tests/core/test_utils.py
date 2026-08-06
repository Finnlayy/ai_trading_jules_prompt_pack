import pytest
from unittest.mock import patch, MagicMock
from app.core.utils import execute_with_db

def test_execute_with_db_success():
    """Test execute_with_db successfully calls the function and closes the session."""
    mock_db = MagicMock()

    # We use a state dictionary to track the generator state instead of
    # setting attributes on a generator or function directly.
    state = {"closed": False}

    def mock_get_db():
        yield mock_db
        state["closed"] = True

    def sample_func(db, arg1, kwarg1=None):
        assert db is mock_db
        assert arg1 == "hello"
        assert kwarg1 == "world"
        return "success"

    # Patch the correct import location
    with patch("app.db.get_db", mock_get_db):
        result = execute_with_db(sample_func, "hello", kwarg1="world")

        assert result == "success"
        assert state["closed"] is True

def test_execute_with_db_exception():
    """Test execute_with_db properly closes the session even if an exception is raised."""
    mock_db = MagicMock()

    state = {"closed": False}

    def mock_get_db():
        yield mock_db
        state["closed"] = True

    def error_func(db):
        raise ValueError("Simulated error")

    # Patch the correct import location
    with patch("app.db.get_db", mock_get_db):
        with pytest.raises(ValueError, match="Simulated error"):
            execute_with_db(error_func)

        assert state["closed"] is True
