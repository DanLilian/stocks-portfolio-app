from collections.abc import Callable
from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from portfolio_service.errors import Conflict, NotFound

MAX_WRITE_ATTEMPTS = 5


def _now() -> datetime:
    """Current time at MongoDB's millisecond precision, so responses match what is stored."""
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def _object_id(portfolio_id: str) -> ObjectId:
    try:
        return ObjectId(portfolio_id)
    except (InvalidId, TypeError):
        raise NotFound(f"Portfolio '{portfolio_id}' not found") from None


def _serialize(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "name": document["name"],
        "description": document["description"],
        "holdings": document["holdings"],
        "created_at": document["created_at"].isoformat(),
        "updated_at": document["updated_at"].isoformat(),
    }


class PortfolioRepository:
    """MongoDB persistence for portfolios and their valuation history.

    Holdings live inside the portfolio document. Every change to them is a
    compare-and-swap on a version counter, so concurrent trades can't overwrite
    each other.
    """

    def __init__(self, db: Database):
        self._portfolios = db["portfolios"]
        self._snapshots = db["valuation_snapshots"]
        self._db = db

    def ensure_indexes(self) -> None:
        self._portfolios.create_index([("name", ASCENDING)], unique=True)
        self._snapshots.create_index([("portfolio_id", ASCENDING), ("taken_at", DESCENDING)])

    def ping(self) -> None:
        self._db.command("ping")

    def create(self, name: str, description: str) -> dict:
        now = _now()
        document = {
            "name": name,
            "description": description,
            "holdings": [],
            "version": 0,
            "created_at": now,
            "updated_at": now,
        }
        try:
            self._portfolios.insert_one(document)
        except DuplicateKeyError:
            raise Conflict(f"A portfolio named '{name}' already exists") from None
        return _serialize(document)

    def list_all(self) -> list[dict]:
        return [_serialize(d) for d in self._portfolios.find().sort("created_at", ASCENDING)]

    def get(self, portfolio_id: str) -> dict:
        document = self._portfolios.find_one({"_id": _object_id(portfolio_id)})
        if document is None:
            raise NotFound(f"Portfolio '{portfolio_id}' not found")
        return _serialize(document)

    def update(self, portfolio_id: str, changes: dict) -> dict:
        try:
            document = self._portfolios.find_one_and_update(
                {"_id": _object_id(portfolio_id)},
                {"$set": {**changes, "updated_at": _now()}},
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            raise Conflict(f"A portfolio named '{changes.get('name')}' already exists") from None
        if document is None:
            raise NotFound(f"Portfolio '{portfolio_id}' not found")
        return _serialize(document)

    def delete(self, portfolio_id: str) -> None:
        object_id = _object_id(portfolio_id)
        result = self._portfolios.delete_one({"_id": object_id})
        if result.deleted_count == 0:
            raise NotFound(f"Portfolio '{portfolio_id}' not found")
        self._snapshots.delete_many({"portfolio_id": object_id})

    def buy(self, portfolio_id: str, symbol: str, quantity: float, price: float) -> dict:
        def apply(holdings: list[dict]) -> list[dict]:
            existing = next((h for h in holdings if h["symbol"] == symbol), None)
            if existing is None:
                return [*holdings, {"symbol": symbol, "quantity": quantity, "average_cost": price}]
            total_quantity = existing["quantity"] + quantity
            total_cost = existing["quantity"] * existing["average_cost"] + quantity * price
            merged = {
                "symbol": symbol,
                "quantity": total_quantity,
                "average_cost": round(total_cost / total_quantity, 6),
            }
            return [merged if h is existing else h for h in holdings]

        return self._change_holdings(portfolio_id, apply)

    def sell(self, portfolio_id: str, symbol: str, quantity: float) -> dict:
        def apply(holdings: list[dict]) -> list[dict]:
            existing = _find_holding(holdings, symbol)
            remaining = existing["quantity"] - quantity
            if remaining < -1e-9:
                raise Conflict(f"Cannot sell {quantity} {symbol}: only {existing['quantity']} held")
            if remaining <= 1e-9:
                return [h for h in holdings if h is not existing]
            return [{**h, "quantity": remaining} if h is existing else h for h in holdings]

        return self._change_holdings(portfolio_id, apply)

    def set_holding(self, portfolio_id: str, symbol: str, quantity: float, average_cost: float) -> dict:
        def apply(holdings: list[dict]) -> list[dict]:
            existing = _find_holding(holdings, symbol)
            replacement = {"symbol": symbol, "quantity": quantity, "average_cost": average_cost}
            return [replacement if h is existing else h for h in holdings]

        return self._change_holdings(portfolio_id, apply)

    def remove_holding(self, portfolio_id: str, symbol: str) -> dict:
        def apply(holdings: list[dict]) -> list[dict]:
            existing = _find_holding(holdings, symbol)
            return [h for h in holdings if h is not existing]

        return self._change_holdings(portfolio_id, apply)

    def _change_holdings(self, portfolio_id: str, apply: Callable[[list[dict]], list[dict]]) -> dict:
        object_id = _object_id(portfolio_id)
        for _ in range(MAX_WRITE_ATTEMPTS):
            current = self._portfolios.find_one({"_id": object_id})
            if current is None:
                raise NotFound(f"Portfolio '{portfolio_id}' not found")

            updated = self._portfolios.find_one_and_update(
                {"_id": object_id, "version": current["version"]},
                {
                    "$set": {"holdings": apply(current["holdings"]), "updated_at": _now()},
                    "$inc": {"version": 1},
                },
                return_document=ReturnDocument.AFTER,
            )
            if updated is not None:
                return _serialize(updated)
        raise Conflict("The portfolio is being modified by another request, please retry")

    def add_snapshot(self, portfolio_id: str, totals: list[dict], status: str) -> None:
        self._snapshots.insert_one(
            {
                "portfolio_id": _object_id(portfolio_id),
                "taken_at": _now(),
                "totals": totals,
                "status": status,
            }
        )

    def list_snapshots(self, portfolio_id: str, limit: int) -> list[dict]:
        self.get(portfolio_id)
        cursor = (
            self._snapshots.find({"portfolio_id": _object_id(portfolio_id)})
            .sort([("taken_at", DESCENDING), ("_id", DESCENDING)])
            .limit(limit)
        )
        return [
            {"taken_at": s["taken_at"].isoformat(), "totals": s["totals"], "status": s["status"]}
            for s in cursor
        ]


def _find_holding(holdings: list[dict], symbol: str) -> dict:
    for holding in holdings:
        if holding["symbol"] == symbol:
            return holding
    raise NotFound(f"No holding for symbol '{symbol}' in this portfolio")
