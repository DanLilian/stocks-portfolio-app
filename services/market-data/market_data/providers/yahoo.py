import logging
from datetime import UTC, datetime
from urllib.parse import quote as url_quote

import requests

from market_data.errors import ProviderUnavailable, SymbolNotFound
from market_data.models import Quote

logger = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo rejects requests that use the default python-requests User-Agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; stocks-portfolio-app/1.0)"}


class YahooProvider:
    """Live quotes from Yahoo Finance's public chart endpoint."""

    def __init__(self, timeout: float = 5.0, session: requests.Session | None = None):
        self._timeout = timeout
        self._session = session or requests.Session()

    def get_quote(self, symbol: str) -> Quote:
        url = CHART_URL.format(symbol=url_quote(symbol, safe=""))
        try:
            response = self._session.get(
                url,
                params={"range": "1d", "interval": "1d"},
                headers=HEADERS,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Yahoo request failed for %s: %s", symbol, exc)
            raise ProviderUnavailable("Market data provider is unreachable") from exc

        if response.status_code == 404:
            raise SymbolNotFound(f"No data found for symbol '{symbol}'")
        if not response.ok:
            logger.warning("Yahoo returned HTTP %s for %s", response.status_code, symbol)
            raise ProviderUnavailable(f"Market data provider returned HTTP {response.status_code}")

        try:
            meta = response.json()["chart"]["result"][0]["meta"]
            return Quote(
                symbol=symbol,
                price=float(meta["regularMarketPrice"]),
                currency=meta["currency"],
                previous_close=meta.get("chartPreviousClose"),
                name=meta.get("longName") or meta.get("shortName"),
                as_of=datetime.fromtimestamp(meta["regularMarketTime"], UTC).isoformat(),
                provider="yahoo",
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Unexpected Yahoo payload for %s: %s", symbol, exc)
            raise ProviderUnavailable("Market data provider returned an unexpected response") from exc
