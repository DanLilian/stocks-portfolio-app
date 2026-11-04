import logging
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

from market_data.errors import APIError, ProviderUnavailable
from market_data.models import Quote
from market_data.providers.base import QuoteProvider

logger = logging.getLogger(__name__)

MAX_WORKERS = 8


class QuoteService:
    """Adds caching and bulk lookups on top of a quote provider.

    Quotes are served from memory for `ttl_seconds`. If the provider goes down
    after that, the last known quote is returned flagged as stale, so a brief
    outage upstream doesn't take down every portfolio valuation.
    """

    def __init__(
        self,
        provider: QuoteProvider,
        ttl_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._provider = provider
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, Quote]] = {}

    def get_quote(self, symbol: str) -> dict:
        with self._lock:
            entry = self._cache.get(symbol)

        if entry and self._clock() - entry[0] < self._ttl:
            return {**entry[1].to_dict(), "cached": True, "stale": False}

        try:
            quote = self._provider.get_quote(symbol)
        except ProviderUnavailable:
            if entry is None:
                raise
            logger.warning("Serving stale quote for %s", symbol)
            return {**entry[1].to_dict(), "cached": True, "stale": True}

        with self._lock:
            self._cache[symbol] = (self._clock(), quote)
        return {**quote.to_dict(), "cached": False, "stale": False}

    def get_quotes(self, symbols: Iterable[str]) -> tuple[dict, dict]:
        """Fetch several symbols concurrently; one bad symbol doesn't fail the rest."""
        unique = list(dict.fromkeys(symbols))

        def fetch(symbol: str) -> tuple[str, dict | None, dict | None]:
            try:
                return symbol, self.get_quote(symbol), None
            except APIError as exc:
                return symbol, None, {"code": exc.code, "message": exc.message}

        quotes, errors = {}, {}
        if not unique:
            return quotes, errors
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(unique))) as pool:
            for symbol, quote, error in pool.map(fetch, unique):
                if quote is not None:
                    quotes[symbol] = quote
                else:
                    errors[symbol] = error
        return quotes, errors
