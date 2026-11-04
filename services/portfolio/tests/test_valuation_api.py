import pytest
import requests
import responses

from portfolio_service.errors import MarketDataUnavailable
from portfolio_service.market_client import MarketDataClient
from portfolio_service.valuation import ValuationService
from portfolio_service.worker import snapshot_all
from tests.helpers import make_quote


def add(client, portfolio_id, symbol, quantity, price):
    client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": symbol, "quantity": quantity, "price": price},
    )


def valuation_url(portfolio_id):
    return f"/api/v1/portfolios/{portfolio_id}/valuation"


def test_empty_portfolio_is_valued_at_nothing(client, portfolio_id):
    response = client.get(valuation_url(portfolio_id))

    assert response.status_code == 200
    assert response.json["status"] == "complete"
    assert response.json["totals"] == []


def test_valuation_computes_positions_and_totals(client, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 10, 100)
    add(client, portfolio_id, "MSFT", 5, 400)
    market.quotes = {"AAPL": make_quote("AAPL", 150, change=2), "MSFT": make_quote("MSFT", 380, change=-1)}

    body = client.get(valuation_url(portfolio_id)).json

    assert body["status"] == "complete"
    apple = body["positions"][0]
    assert apple["market_value"] == 1500
    assert apple["cost_basis"] == 1000
    assert apple["unrealized_pnl"] == 500
    assert apple["unrealized_pnl_percent"] == 50
    assert apple["day_change"] == 20
    assert body["totals"] == [
        {
            "currency": "USD",
            "market_value": 3400,
            "cost_basis": 3000,
            "unrealized_pnl": 400,
            "unrealized_pnl_percent": 13.33,
            "day_change": 15,
        }
    ]


def test_valuation_reflects_price_changes(client, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 10, 100)

    market.quotes = {"AAPL": make_quote("AAPL", 150)}
    assert client.get(valuation_url(portfolio_id)).json["totals"][0]["market_value"] == 1500

    market.quotes = {"AAPL": make_quote("AAPL", 160)}
    assert client.get(valuation_url(portfolio_id)).json["totals"][0]["market_value"] == 1600


def test_totals_are_not_summed_across_currencies(client, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 1, 100)
    add(client, portfolio_id, "VOD.L", 1, 50)
    market.quotes = {
        "AAPL": make_quote("AAPL", 100),
        "VOD.L": make_quote("VOD.L", 70, currency="GBP"),
    }

    totals = {
        t["currency"]: t["market_value"] for t in client.get(valuation_url(portfolio_id)).json["totals"]
    }

    assert totals == {"USD": 100, "GBP": 70}


def test_unpriced_holding_makes_valuation_partial(client, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 1, 100)
    add(client, portfolio_id, "DELISTED", 1, 100)
    market.quotes = {"AAPL": make_quote("AAPL", 120)}

    body = client.get(valuation_url(portfolio_id)).json

    assert body["status"] == "partial"
    assert body["totals"][0]["market_value"] == 120
    assert body["positions"][1]["market_value"] is None
    assert body["unpriced"]["DELISTED"]["code"] == "symbol_not_found"


def test_stale_quote_is_flagged(client, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 1, 100)
    market.quotes = {"AAPL": make_quote("AAPL", 120, stale=True)}
    assert client.get(valuation_url(portfolio_id)).json["positions"][0]["stale"] is True


def test_market_service_outage_returns_503(client, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 1, 100)
    market.down = True

    response = client.get(valuation_url(portfolio_id))

    assert response.status_code == 503
    assert response.json["error"]["code"] == "market_data_unavailable"


def test_zero_cost_position_has_no_percentage(client, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 1, 0)
    market.quotes = {"AAPL": make_quote("AAPL", 100)}
    assert client.get(valuation_url(portfolio_id)).json["positions"][0]["unrealized_pnl_percent"] is None


def test_worker_records_history_newest_first(client, repository, market, portfolio_id):
    client.post("/api/v1/portfolios", json={"name": "Empty"})
    add(client, portfolio_id, "AAPL", 10, 100)
    valuation = ValuationService(market)

    market.quotes = {"AAPL": make_quote("AAPL", 150)}
    assert snapshot_all(repository, valuation) == 1
    market.quotes = {"AAPL": make_quote("AAPL", 160)}
    assert snapshot_all(repository, valuation) == 1

    snapshots = client.get(f"/api/v1/portfolios/{portfolio_id}/history").json["snapshots"]
    assert [s["totals"][0]["market_value"] for s in snapshots] == [1600, 1500]
    limited = client.get(f"/api/v1/portfolios/{portfolio_id}/history?limit=1").json["snapshots"]
    assert len(limited) == 1


def test_worker_skips_portfolios_it_cannot_price(client, repository, market, portfolio_id):
    add(client, portfolio_id, "AAPL", 10, 100)
    valuation = ValuationService(market)

    assert snapshot_all(repository, valuation) == 0
    market.down = True
    assert snapshot_all(repository, valuation) == 0


def test_history_of_missing_portfolio_returns_404(client):
    assert client.get("/api/v1/portfolios/507f1f77bcf86cd799439011/history").status_code == 404


QUOTES_URL = "http://market-data:8001/api/v1/quotes"


@responses.activate
def test_market_client_batches_large_requests():
    responses.get(QUOTES_URL, json={"quotes": {}, "errors": {}})
    MarketDataClient("http://market-data:8001").get_quotes([f"S{i}" for i in range(120)])
    assert len(responses.calls) == 3


@responses.activate
def test_market_client_merges_results():
    responses.get(QUOTES_URL, json={"quotes": {"AAPL": {"price": 1}}, "errors": {"X": {"code": "nope"}}})
    quotes, errors = MarketDataClient("http://market-data:8001/").get_quotes(["AAPL", "X"])
    assert quotes == {"AAPL": {"price": 1}}
    assert errors == {"X": {"code": "nope"}}


@responses.activate
@pytest.mark.parametrize(
    "mock",
    [{"status": 500}, {"body": requests.ConnectionError("boom")}, {"body": "not json"}],
)
def test_market_client_failures_are_reported_as_unavailable(mock):
    responses.get(QUOTES_URL, **mock)
    with pytest.raises(MarketDataUnavailable):
        MarketDataClient("http://market-data:8001").get_quotes(["AAPL"])
