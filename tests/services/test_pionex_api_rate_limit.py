from unittest.mock import Mock, patch, call
import pytest
from app.services.pionex_api import PionexClient, PionexCredentials, PionexAPIError


def _mock_response(status_code: int, payload: dict):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def test_429_rate_limit_retries_with_backoff():
    client = PionexClient(PionexCredentials(api_key="k", api_secret="s"))

    responses = [
        _mock_response(429, {"result": False, "message": "rate limit"}),
        _mock_response(429, {"result": False, "message": "rate limit"}),
        _mock_response(200, {"result": True, "data": {"balances": []}}),
    ]

    with patch.object(client.session, "get", side_effect=responses) as get_mock:
        with patch("time.sleep") as sleep_mock:
            result = client.get_spot_balances()

    assert result == []
    assert get_mock.call_count == 3
    assert sleep_mock.call_count == 2
    assert sleep_mock.call_args_list == [call(1), call(2)]


def test_500_server_error_retries_then_raises():
    client = PionexClient(PionexCredentials(api_key="k", api_secret="s"))

    responses = [
        _mock_response(500, {"result": False, "message": "internal error"}),
        _mock_response(500, {"result": False, "message": "internal error"}),
        _mock_response(500, {"result": False, "message": "internal error"}),
        _mock_response(500, {"result": False, "message": "internal error"}),
    ]

    with patch.object(client.session, "get", side_effect=responses):
        with patch("time.sleep"):
            with pytest.raises(PionexAPIError) as exc:
                client.get_spot_balances()

    assert exc.value.retryable is True
    assert exc.value.status_code == 500
