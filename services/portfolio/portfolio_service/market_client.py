import logging
import os
from urllib.parse import urljoin

import requests

from portfolio_service.errors import MarketDataUnavailable

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


class MarketDataClient:
    """HTTP client for the market data microservice."""

    def __init__(self, base_url: str, timeout: float = 10.0, session: requests.Session | None = None):
        self._url = urljoin(base_url.rstrip("/") + "/", "api/v1/quotes")
        self._timeout = timeout
        self._session = session or requests.Session()

    @classmethod
    def from_env(cls) -> "MarketDataClient":
        return cls(os.getenv("MARKET_DATA_URL", "http://localhost:8001"))

    def get_quotes(self, symbols: list[str]) -> tuple[dict, dict]:
        """Return (quotes, errors), each keyed by symbol."""
        quotes, errors = {}, {}
        for start in range(0, len(symbols), BATCH_SIZE):
            batch = symbols[start : start + BATCH_SIZE]
            payload = self._fetch_batch(batch)
            quotes.update(payload["quotes"])
            errors.update(payload["errors"])
        return quotes, errors

    def _fetch_batch(self, symbols: list[str]) -> dict:
        try:
            response = self._session.get(
                self._url, params={"symbols": ",".join(symbols)}, timeout=self._timeout
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Market data request failed: %s", exc)
            raise MarketDataUnavailable("The market data service is unavailable") from exc
