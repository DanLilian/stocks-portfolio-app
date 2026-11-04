import pytest

from market_data import create_app
from market_data.providers import StaticProvider, build_provider
from market_data.quote_service import QuoteService


@pytest.fixture
def client():
    return create_app(QuoteService(StaticProvider())).test_client()


def test_health(client):
    assert client.get("/health").json == {"status": "ok", "service": "market-data"}


def test_get_quote_includes_day_change(client):
    response = client.get("/api/v1/quotes/aapl")

    assert response.status_code == 200
    assert response.json["symbol"] == "AAPL"
    assert response.json["price"] == 190.0
    assert response.json["change"] == 2.0
    assert response.json["change_percent"] == pytest.approx(1.0638, abs=1e-4)


def test_unknown_symbol_returns_404(client):
    response = client.get("/api/v1/quotes/NOPE")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "symbol_not_found"


@pytest.mark.parametrize("symbol", ["bad symbol", "a!b", "A" * 20])
def test_invalid_symbol_returns_400(client, symbol):
    response = client.get(f"/api/v1/quotes/{symbol}")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_symbol"


def test_bulk_quotes_report_per_symbol_errors(client):
    response = client.get("/api/v1/quotes?symbols=AAPL,msft,NOPE,b@d")

    assert response.status_code == 200
    assert set(response.json["quotes"]) == {"AAPL", "MSFT"}
    assert response.json["errors"]["NOPE"]["code"] == "symbol_not_found"
    assert response.json["errors"]["b@d"]["code"] == "invalid_symbol"


def test_bulk_quotes_require_symbols(client):
    assert client.get("/api/v1/quotes").status_code == 400


def test_bulk_quotes_limit_request_size(client):
    symbols = ",".join(f"S{i}" for i in range(51))
    assert client.get(f"/api/v1/quotes?symbols={symbols}").status_code == 400


def test_unknown_route_returns_json_error(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "not_found"


def test_build_provider_rejects_unknown_name():
    with pytest.raises(ValueError):
        build_provider("nope")
