from unittest.mock import Mock, patch

import pytest

from app.services.pionex_api import (
    PionexAPIError,
    PionexClient,
    PionexCredentials,
)


def _mock_response(status_code: int, payload: dict):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def test_private_request_adds_auth_headers_and_timestamp():
    client = PionexClient(
        PionexCredentials(
            api_key="key-123",
            api_secret="secret-123",
            base_url="https://api.pionex.com",
            timeout_seconds=5.0,
        )
    )
    response = _mock_response(200, {"result": True, "data": {"balances": []}})

    with patch.object(client.session, "get", return_value=response) as get_mock:
        client.get_spot_balances()

    kwargs = get_mock.call_args.kwargs
    headers = kwargs["headers"]
    params = kwargs["params"]
    assert headers["PIONEX-KEY"] == "key-123"
    assert "PIONEX-SIGNATURE" in headers
    assert isinstance(params["timestamp"], int)


def test_place_spot_market_buy_uses_amount_field():
    client = PionexClient(PionexCredentials(api_key="k", api_secret="s"))
    response = _mock_response(200, {"result": True, "data": {"orderId": "abc"}})

    with patch.object(client.session, "post", return_value=response) as post_mock:
        data = client.place_spot_market_buy(symbol="BTC_USDT", amount_usdt=25.0)

    assert data["orderId"] == "abc"
    sent_body = post_mock.call_args.kwargs["data"]
    assert '"amount":"25.0"' in sent_body
    assert '"size"' not in sent_body


def test_server_error_is_retryable():
    client = PionexClient(PionexCredentials(api_key="k", api_secret="s"))
    response = _mock_response(502, {"result": False, "message": "bad gateway"})

    with patch.object(client.session, "get", return_value=response):
        with pytest.raises(PionexAPIError) as exc:
            client.get_spot_balances()

    assert exc.value.retryable is True
    assert exc.value.status_code == 502


def test_get_futures_positions_uses_account_positions_endpoint():
    client = PionexClient(PionexCredentials(api_key="k", api_secret="s"))
    response = _mock_response(
        200,
        {
            "result": True,
            "data": {
                "positions": [
                    {"symbol": "ZEC_USDT_PERP", "initialMargin": "7.5"},
                ]
            },
        },
    )

    with patch.object(client.session, "get", return_value=response) as get_mock:
        positions = client.get_futures_positions(symbol="ZEC_USDT_PERP")

    assert positions[0]["symbol"] == "ZEC_USDT_PERP"
    assert get_mock.call_args.args[0].endswith("/uapi/v1/account/positions")
    assert get_mock.call_args.kwargs["params"]["symbol"] == "ZEC_USDT_PERP"


def test_get_bot_orders_uses_bot_orders_endpoint():
    client = PionexClient(PionexCredentials(api_key="k", api_secret="s"))
    response = _mock_response(
        200,
        {
            "result": True,
            "data": {
                "results": [
                    {"buOrderType": "futures_grid", "base": "ZEC", "quote": "USDT"},
                ]
            },
        },
    )

    with patch.object(client.session, "get", return_value=response) as get_mock:
        data = client.get_bot_orders(status="running", base="zec", quote="usdt")

    assert data["results"][0]["base"] == "ZEC"
    assert get_mock.call_args.args[0].endswith("/api/v1/bot/orders")
    assert get_mock.call_args.kwargs["params"]["status"] == "running"
    assert get_mock.call_args.kwargs["params"]["base"] == "ZEC"
    assert get_mock.call_args.kwargs["params"]["quote"] == "USDT"


def test_get_futures_grid_order_uses_bot_detail_endpoint():
    client = PionexClient(PionexCredentials(api_key="k", api_secret="s"))
    response = _mock_response(
        200,
        {
            "result": True,
            "data": {
                "buOrderId": "bot-1",
                "buOrderType": "futures_grid",
                "buOrderData": {"marginBalance": "9.5"},
            },
        },
    )

    with patch.object(client.session, "get", return_value=response) as get_mock:
        data = client.get_futures_grid_order("bot-1")

    assert data["buOrderId"] == "bot-1"
    assert get_mock.call_args.args[0].endswith("/api/v1/bot/orders/futuresGrid/order")
    assert get_mock.call_args.kwargs["params"]["buOrderId"] == "bot-1"
