from datetime import UTC, datetime

from market_data.errors import SymbolNotFound
from market_data.models import Quote

PRICES = {
    "AAPL": (190.0, 188.0, "Apple Inc."),
    "GOOGL": (140.0, 141.0, "Alphabet Inc."),
    "MSFT": (410.0, 405.0, "Microsoft Corporation"),
    "NVDA": (120.0, 118.5, "NVIDIA Corporation"),
    "TSLA": (250.0, 255.0, "Tesla, Inc."),
}


class StaticProvider:
    """Fixed prices for local development and CI, where a live feed would make runs flaky."""

    def get_quote(self, symbol: str) -> Quote:
        if symbol not in PRICES:
            raise SymbolNotFound(f"No data found for symbol '{symbol}'")
        price, previous_close, name = PRICES[symbol]
        return Quote(
            symbol=symbol,
            price=price,
            currency="USD",
            previous_close=previous_close,
            name=name,
            as_of=datetime.now(UTC).isoformat(),
            provider="static",
        )
