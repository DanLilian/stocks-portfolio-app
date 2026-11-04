import pytest
import requests
import responses

from market_data.errors import ProviderUnavailable, SymbolNotFound
from market_data.providers.yahoo import CHART_URL, YahooProvider

PAYLOAD = {
    "chart": {
        "result": [
            {
                "meta": {
                    "symbol": "AAPL",
                    "currency": "USD",
                    "regularMarketPrice": 190.5,
                    "chartPreviousClose": 188.0,
                    "regularMarketTime": 1735689600,
                    "longName": "Apple Inc.",
                }
            }
        ],
        "error": None,
    }
}


@responses.activate
def test_parses_quote():
    responses.get(CHART_URL.format(symbol="AAPL"), json=PAYLOAD)

    quote = YahooProvider().get_quote("AAPL")

    assert quote.price == 190.5
    assert quote.previous_close == 188.0
    assert quote.currency == "USD"
    assert quote.name == "Apple Inc."
    assert quote.as_of == "2025-01-01T00:00:00+00:00"


@responses.activate
def test_symbol_is_escaped_in_url():
    responses.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC", json=PAYLOAD)
    YahooProvider().get_quote("^GSPC")
    assert len(responses.calls) == 1


@responses.activate
def test_404_means_unknown_symbol():
    responses.get(CHART_URL.format(symbol="NOPE"), status=404, json={"chart": {"result": None}})
    with pytest.raises(SymbolNotFound):
        YahooProvider().get_quote("NOPE")


@responses.activate
def test_rate_limit_is_an_outage():
    responses.get(CHART_URL.format(symbol="AAPL"), status=429)
    with pytest.raises(ProviderUnavailable):
        YahooProvider().get_quote("AAPL")


@responses.activate
def test_network_error_is_an_outage():
    responses.get(CHART_URL.format(symbol="AAPL"), body=requests.ConnectionError("boom"))
    with pytest.raises(ProviderUnavailable):
        YahooProvider().get_quote("AAPL")


@responses.activate
def test_malformed_payload_is_an_outage():
    responses.get(CHART_URL.format(symbol="AAPL"), json={"chart": {"result": []}})
    with pytest.raises(ProviderUnavailable):
        YahooProvider().get_quote("AAPL")
