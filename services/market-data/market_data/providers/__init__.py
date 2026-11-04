from market_data.providers.base import QuoteProvider
from market_data.providers.static import StaticProvider
from market_data.providers.yahoo import YahooProvider


def build_provider(name: str) -> QuoteProvider:
    providers = {"yahoo": YahooProvider, "static": StaticProvider}
    try:
        return providers[name.lower()]()
    except KeyError:
        raise ValueError(f"Unknown market data provider: {name}") from None


__all__ = ["QuoteProvider", "StaticProvider", "YahooProvider", "build_provider"]
