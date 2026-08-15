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
    # Mocking os.name breaks pathlib on Windows (PosixPath instantiation);
    # branch on the real platform instead.
    import sys

    response = None
    if sys.platform == 'win32':
        mock_start = mocker.patch('os.startfile', create=True)
        response = client.post("/academy/policy/onnx/open-folder")
        mock_start.assert_called_once()
    else:
        mock_run = mocker.patch('subprocess.run')
        response = client.post("/academy/policy/onnx/open-folder")
        mock_run.assert_called_once()

    assert response.status_code == 200
    assert response.json()["status"] == "success"
