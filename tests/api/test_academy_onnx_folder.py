import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import get_current_user
import os
import sys
import shutil

app.dependency_overrides[get_current_user] = lambda: {'email': 'test@example.com'}
client = TestClient(app)

def test_open_onnx_folder(mocker):
    # Mock os.startfile for Windows, and subprocess.run for Posix/Mac
    mocker.patch('os.name', 'posix')
    mocker.patch('sys.platform', 'linux')
    mock_run = mocker.patch('subprocess.run')

    response = client.post("/academy/policy/onnx/open-folder")

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Check that subprocess.run was called
    mock_run.assert_called_once()
