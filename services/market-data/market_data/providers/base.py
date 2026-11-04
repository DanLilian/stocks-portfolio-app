from typing import Protocol

from market_data.models import Quote


class QuoteProvider(Protocol):
    """A source of quotes.

    Implementations raise SymbolNotFound when the symbol does not exist and
    ProviderUnavailable when the upstream cannot answer right now.
    """

    def get_quote(self, symbol: str) -> Quote: ...
