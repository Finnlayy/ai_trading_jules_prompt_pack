<<<<<<< HEAD
import pytest
from unittest.mock import patch, MagicMock
from app.services.bybit_api import BybitAPIClient, BybitCredentials, BybitAPIError

def test_bybit_credentials_live_blocked():
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=False)
    with pytest.raises(BybitAPIError, match="LIVE trading is blocked"):
        BybitAPIClient(creds)

def test_bybit_client_init_success():
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)
    assert client.base_url == "https://api-testnet.bybit.com"

@patch('app.services.bybit_api.requests.get')
def test_bybit_get_wallet_balance_success(mock_get):
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)

    mock_response = MagicMock()
    mock_response.json.return_value = {"retCode": 0, "result": {"list": [{"totalEquity": "1000"}]}}
    mock_get.return_value = mock_response

    result = client.get_wallet_balance()
    assert result == {"list": [{"totalEquity": "1000"}]}
    mock_get.assert_called_once()

@patch('app.services.bybit_api.requests.get')
def test_bybit_api_error_handling(mock_get):
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)

    mock_response = MagicMock()
    mock_response.json.return_value = {"retCode": 10001, "retMsg": "Invalid API key"}
    mock_get.return_value = mock_response

    with pytest.raises(BybitAPIError, match="Bybit API error"):
        client.get_wallet_balance()

@patch('app.services.bybit_api.requests.post')
def test_bybit_place_order(mock_post):
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)

    mock_response = MagicMock()
    mock_response.json.return_value = {"retCode": 0, "result": {"orderId": "12345"}}
    mock_post.return_value = mock_response

    result = client.place_order(symbol="BTCUSDT", side="Buy", qty="0.1")
    assert result == {"orderId": "12345"}
    mock_post.assert_called_once()

@patch('app.services.bybit_api.requests.get')
def test_bybit_get_open_orders(mock_get):
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)

    mock_response = MagicMock()
    mock_response.json.return_value = {"retCode": 0, "result": {"list": [{"orderId": "123"}]}}
    mock_get.return_value = mock_response

    result = client.get_open_orders(symbol="BTCUSDT")
    assert result == {"list": [{"orderId": "123"}]}
    mock_get.assert_called_once()

@patch('app.services.bybit_api.requests.get')
def test_bybit_get_position(mock_get):
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)

    mock_response = MagicMock()
    mock_response.json.return_value = {"retCode": 0, "result": {"list": [{"symbol": "BTCUSDT"}]}}
    mock_get.return_value = mock_response

    result = client.get_position(symbol="BTCUSDT")
    assert result == {"list": [{"symbol": "BTCUSDT"}]}
    mock_get.assert_called_once()

@patch('app.services.bybit_api.requests.post')
def test_bybit_cancel_order(mock_post):
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)

    mock_response = MagicMock()
    mock_response.json.return_value = {"retCode": 0, "result": {"orderId": "123"}}
    mock_post.return_value = mock_response

    result = client.cancel_order(symbol="BTCUSDT", order_id="123")
    assert result == {"orderId": "123"}
    mock_post.assert_called_once()

@patch('app.services.bybit_api.requests.post')
def test_bybit_set_trading_stop(mock_post):
    creds = BybitCredentials(api_key="test", api_secret="test", testnet=True)
    client = BybitAPIClient(creds)

    mock_response = MagicMock()
    mock_response.json.return_value = {"retCode": 0, "result": {}}
    mock_post.return_value = mock_response

    result = client.set_trading_stop(symbol="BTCUSDT", stop_loss="9000")
    assert result == {}
    mock_post.assert_called_once()
=======

import hashlib
import hmac
from unittest.mock import Mock, patch
import pytest

from app.services.bybit_api import (
    BybitAPIClient,
    BybitCredentials,
    BybitAPIError,
)

@pytest.fixture
def test_creds():
    return BybitCredentials(api_key="test_key", api_secret="test_secret", testnet=True)

@pytest.fixture
def client(test_creds):
    return BybitAPIClient(test_creds)

def test_init_live_trading_blocked():
    with pytest.raises(BybitAPIError, match="LIVE trading is blocked"):
        BybitAPIClient(BybitCredentials(api_key="key", api_secret="secret", testnet=False))

@patch("app.services.bybit_api.time.time")
def test_generate_signature(mock_time, client):
    mock_time.return_value = 1000.0
    payload = '{"test":"payload"}'
    timestamp, signature = client._generate_signature(payload)

    assert timestamp == "1000000"

    expected_param_str = timestamp + "test_key" + payload
    expected_signature = hmac.new(
        b"test_secret",
        expected_param_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert signature == expected_signature

@patch("app.services.bybit_api.requests.get")
def test_request_success_get(mock_get, client):
    mock_response = Mock()
    mock_response.json.return_value = {"retCode": 0, "result": {"foo": "bar"}}
    mock_get.return_value = mock_response

    result = client._request("GET", "/test/path", {"param1": "value1"})

    assert result == {"foo": "bar"}
    mock_get.assert_called_once()

@patch("app.services.bybit_api.requests.post")
def test_request_success_post(mock_post, client):
    mock_response = Mock()
    mock_response.json.return_value = {"retCode": 0, "result": {"foo": "bar"}}
    mock_post.return_value = mock_response

    result = client._request("POST", "/test/path", {"param1": "value1"})

    assert result == {"foo": "bar"}
    mock_post.assert_called_once()

@patch("app.services.bybit_api.requests.get")
def test_request_api_error(mock_get, client):
    mock_response = Mock()
    mock_response.json.return_value = {"retCode": 10001, "retMsg": "error"}
    mock_get.return_value = mock_response

    with pytest.raises(BybitAPIError, match="Bybit API error"):
        client._request("GET", "/test/path")

@patch.object(BybitAPIClient, "_request")
def test_place_order(mock_request, client):
    client.place_order("BTCUSDT", "Buy")

    mock_request.assert_called_once_with(
        "POST",
        "/v5/order/create",
        {
            "category": "linear",
            "symbol": "BTCUSDT",
            "side": "Buy",
            "orderType": "Market",
            "qty": "0",
            "timeInForce": "GTC",
        }
    )

@patch.object(BybitAPIClient, "_request")
def test_get_open_orders(mock_request, client):
    client.get_open_orders()
    mock_request.assert_called_once_with("GET", "/v5/order/realtime", {"category": "linear"})

    mock_request.reset_mock()
    client.get_open_orders("BTCUSDT")
    mock_request.assert_called_once_with("GET", "/v5/order/realtime", {"category": "linear", "symbol": "BTCUSDT"})

@patch.object(BybitAPIClient, "_request")
def test_get_position(mock_request, client):
    client.get_position("BTCUSDT")
    mock_request.assert_called_once_with("GET", "/v5/position/list", {"category": "linear", "symbol": "BTCUSDT"})

@patch.object(BybitAPIClient, "_request")
def test_cancel_order(mock_request, client):
    client.cancel_order("BTCUSDT", "123")
    mock_request.assert_called_once_with("POST", "/v5/order/cancel", {"category": "linear", "symbol": "BTCUSDT", "orderId": "123"})

@patch.object(BybitAPIClient, "_request")
def test_set_trading_stop(mock_request, client):
    client.set_trading_stop("BTCUSDT", stop_loss="40000")
    mock_request.assert_called_once_with("POST", "/v5/position/trading-stop", {"category": "linear", "symbol": "BTCUSDT", "stopLoss": "40000"})

@patch.object(BybitAPIClient, "_request")
def test_get_wallet_balance(mock_request, client):
    client.get_wallet_balance()
    mock_request.assert_called_once_with("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
>>>>>>> main
