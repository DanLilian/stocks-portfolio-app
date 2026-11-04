import mongomock
import pytest

from portfolio_service import create_app
from portfolio_service.errors import MarketDataUnavailable
from portfolio_service.repository import PortfolioRepository


class FakeMarketClient:
    def __init__(self):
        self.quotes = {}
        self.down = False

    def get_quotes(self, symbols):
        if self.down:
            raise MarketDataUnavailable("The market data service is unavailable")
        quotes = {s: self.quotes[s] for s in symbols if s in self.quotes}
        errors = {
            s: {"code": "symbol_not_found", "message": "No data found"}
            for s in symbols
            if s not in self.quotes
        }
        return quotes, errors


@pytest.fixture
def repository():
    repo = PortfolioRepository(mongomock.MongoClient(tz_aware=True)["test"])
    repo.ensure_indexes()
    return repo


@pytest.fixture
def market():
    return FakeMarketClient()


@pytest.fixture
def client(repository, market):
    return create_app(repository=repository, market_client=market).test_client()


@pytest.fixture
def portfolio_id(client):
    return client.post("/api/v1/portfolios", json={"name": "Retirement"}).json["id"]
