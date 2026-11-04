import pytest

from market_data.errors import ProviderUnavailable, SymbolNotFound
from market_data.models import Quote
from market_data.quote_service import QuoteService


class FakeProvider:
    def __init__(self):
        self.calls = 0
        self.failure = None

    def get_quote(self, symbol):
        self.calls += 1
        if self.failure:
            raise self.failure
        return Quote(symbol, 100.0, "USD", 90.0, "Fake Inc.", "2025-01-01T00:00:00+00:00", "fake")


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def service(provider, clock):
    return QuoteService(provider, ttl_seconds=30, clock=clock)


def test_second_lookup_within_ttl_uses_cache(service, provider):
    assert service.get_quote("AAPL")["cached"] is False
    assert service.get_quote("AAPL")["cached"] is True
    assert provider.calls == 1


def test_lookup_after_ttl_refreshes(service, provider, clock):
    service.get_quote("AAPL")
    clock.now = 31
    assert service.get_quote("AAPL")["cached"] is False
    assert provider.calls == 2


def test_serves_stale_quote_when_provider_is_down(service, provider, clock):
    service.get_quote("AAPL")
    clock.now = 31
    provider.failure = ProviderUnavailable("down")

    quote = service.get_quote("AAPL")

    assert quote["stale"] is True
    assert quote["price"] == 100.0


def test_provider_outage_without_cached_quote_raises(service, provider):
    provider.failure = ProviderUnavailable("down")
    with pytest.raises(ProviderUnavailable):
        service.get_quote("AAPL")


def test_unknown_symbol_is_not_served_from_stale_cache(service, provider, clock):
    service.get_quote("AAPL")
    clock.now = 31
    provider.failure = SymbolNotFound("delisted")
    with pytest.raises(SymbolNotFound):
        service.get_quote("AAPL")


def test_bulk_lookup_separates_quotes_from_errors(service, provider):
    class PartialProvider(FakeProvider):
        def get_quote(self, symbol):
            if symbol == "NOPE":
                raise SymbolNotFound("no such symbol")
            return super().get_quote(symbol)

    service = QuoteService(PartialProvider())

    quotes, errors = service.get_quotes(["AAPL", "NOPE", "AAPL"])

    assert list(quotes) == ["AAPL"]
    assert errors["NOPE"]["code"] == "symbol_not_found"
