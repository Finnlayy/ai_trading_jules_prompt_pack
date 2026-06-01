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
