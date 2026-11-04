import re
from dataclasses import asdict, dataclass

from market_data.errors import InvalidSymbol

# Covers plain tickers (AAPL), share classes (BRK-B), exchange suffixes (VOD.L),
# indices (^GSPC), and FX or crypto pairs (EURUSD=X, BTC-USD).
SYMBOL_PATTERN = re.compile(r"^\^?[A-Z0-9][A-Z0-9.\-=]{0,14}$")


def normalize_symbol(raw: str) -> str:
    symbol = raw.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise InvalidSymbol(f"'{raw}' is not a valid stock symbol")
    return symbol


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    currency: str
    previous_close: float | None
    name: str | None
    as_of: str
    provider: str

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.previous_close:
            change = self.price - self.previous_close
            data["change"] = round(change, 4)
            data["change_percent"] = round(change / self.previous_close * 100, 4)
        else:
            data["change"] = None
            data["change_percent"] = None
        return data
