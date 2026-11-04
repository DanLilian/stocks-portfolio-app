def make_quote(symbol, price, currency="USD", change=1.0, stale=False):
    return {
        "symbol": symbol,
        "price": price,
        "currency": currency,
        "change": change,
        "stale": stale,
        "as_of": "2025-01-01T00:00:00+00:00",
    }
