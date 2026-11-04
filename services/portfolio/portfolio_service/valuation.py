from datetime import UTC, datetime

from portfolio_service.market_client import MarketDataClient


def _percent(part: float, whole: float) -> float | None:
    return round(part / whole * 100, 2) if whole else None


class ValuationService:
    """Values a portfolio's holdings against live quotes.

    Totals are grouped by currency because the service has no FX conversion, and
    adding USD to GBP would produce a meaningless number. A holding with no
    available quote is reported with null values and left out of the totals, and
    the valuation's status becomes "partial".
    """

    def __init__(self, market_client: MarketDataClient):
        self._market_client = market_client

    def value(self, portfolio: dict) -> dict:
        symbols = [h["symbol"] for h in portfolio["holdings"]]
        quotes, errors = self._market_client.get_quotes(symbols) if symbols else ({}, {})

        positions = [self._value_position(h, quotes.get(h["symbol"])) for h in portfolio["holdings"]]
        priced = [p for p in positions if p["market_value"] is not None]

        return {
            "portfolio_id": portfolio["id"],
            "name": portfolio["name"],
            "valued_at": datetime.now(UTC).isoformat(),
            "status": "complete" if len(priced) == len(positions) else "partial",
            "totals": self._totals(priced),
            "positions": positions,
            "unpriced": errors,
        }

    @staticmethod
    def _value_position(holding: dict, quote: dict | None) -> dict:
        quantity, average_cost = holding["quantity"], holding["average_cost"]
        cost_basis = quantity * average_cost
        position = {
            "symbol": holding["symbol"],
            "quantity": quantity,
            "average_cost": average_cost,
            "cost_basis": round(cost_basis, 2),
            "price": None,
            "currency": None,
            "market_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_percent": None,
            "day_change": None,
            "stale": None,
            "as_of": None,
        }
        if quote is None:
            return position

        market_value = quantity * quote["price"]
        pnl = market_value - cost_basis
        change = quote.get("change")
        return {
            **position,
            "price": quote["price"],
            "currency": quote["currency"],
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(pnl, 2),
            "unrealized_pnl_percent": _percent(pnl, cost_basis),
            "day_change": round(quantity * change, 2) if change is not None else None,
            "stale": quote.get("stale", False),
            "as_of": quote.get("as_of"),
        }

    @staticmethod
    def _totals(priced: list[dict]) -> list[dict]:
        by_currency: dict[str, dict] = {}
        for position in priced:
            totals = by_currency.setdefault(
                position["currency"],
                {"currency": position["currency"], "market_value": 0.0, "cost_basis": 0.0, "day_change": 0.0},
            )
            totals["market_value"] += position["market_value"]
            totals["cost_basis"] += position["cost_basis"]
            totals["day_change"] += position["day_change"] or 0.0

        results = []
        for totals in by_currency.values():
            pnl = totals["market_value"] - totals["cost_basis"]
            results.append(
                {
                    "currency": totals["currency"],
                    "market_value": round(totals["market_value"], 2),
                    "cost_basis": round(totals["cost_basis"], 2),
                    "unrealized_pnl": round(pnl, 2),
                    "unrealized_pnl_percent": _percent(pnl, totals["cost_basis"]),
                    "day_change": round(totals["day_change"], 2),
                }
            )
        return results
