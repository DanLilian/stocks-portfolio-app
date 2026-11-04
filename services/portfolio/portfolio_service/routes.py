from flask import Blueprint, current_app, jsonify, request
from pymongo.errors import PyMongoError

from portfolio_service.errors import NotFound
from portfolio_service.repository import PortfolioRepository
from portfolio_service.schemas import (
    HoldingBuy,
    HoldingSell,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioUpdate,
    normalize_symbol,
)
from portfolio_service.valuation import ValuationService

api = Blueprint("api", __name__)

DEFAULT_HISTORY_LIMIT = 100
MAX_HISTORY_LIMIT = 1000


def _repository() -> PortfolioRepository:
    return current_app.extensions["repository"]


def _valuation() -> ValuationService:
    return current_app.extensions["valuation"]


def _path_symbol(symbol: str) -> str:
    try:
        return normalize_symbol(symbol)
    except ValueError:
        raise NotFound(f"No holding for symbol '{symbol}' in this portfolio") from None


@api.get("/health")
def health():
    try:
        _repository().ping()
    except PyMongoError:
        return jsonify(status="unavailable", service="portfolio", database="down"), 503
    return jsonify(status="ok", service="portfolio", database="up")


@api.post("/api/v1/portfolios")
def create_portfolio():
    body = PortfolioCreate.model_validate(request.get_json())
    portfolio = _repository().create(body.name, body.description)
    return jsonify(portfolio), 201, {"Location": f"/api/v1/portfolios/{portfolio['id']}"}


@api.get("/api/v1/portfolios")
def list_portfolios():
    return jsonify(portfolios=_repository().list_all())


@api.get("/api/v1/portfolios/<portfolio_id>")
def get_portfolio(portfolio_id: str):
    return jsonify(_repository().get(portfolio_id))


@api.patch("/api/v1/portfolios/<portfolio_id>")
def update_portfolio(portfolio_id: str):
    changes = PortfolioUpdate.model_validate(request.get_json()).model_dump(exclude_none=True)
    return jsonify(_repository().update(portfolio_id, changes))


@api.delete("/api/v1/portfolios/<portfolio_id>")
def delete_portfolio(portfolio_id: str):
    _repository().delete(portfolio_id)
    return "", 204


@api.post("/api/v1/portfolios/<portfolio_id>/holdings")
def buy_holding(portfolio_id: str):
    body = HoldingBuy.model_validate(request.get_json())
    return jsonify(_repository().buy(portfolio_id, body.symbol, body.quantity, body.price)), 201


@api.put("/api/v1/portfolios/<portfolio_id>/holdings/<symbol>")
def set_holding(portfolio_id: str, symbol: str):
    body = HoldingUpdate.model_validate(request.get_json())
    portfolio = _repository().set_holding(
        portfolio_id, _path_symbol(symbol), body.quantity, body.average_cost
    )
    return jsonify(portfolio)


@api.post("/api/v1/portfolios/<portfolio_id>/holdings/<symbol>/sell")
def sell_holding(portfolio_id: str, symbol: str):
    body = HoldingSell.model_validate(request.get_json())
    return jsonify(_repository().sell(portfolio_id, _path_symbol(symbol), body.quantity))


@api.delete("/api/v1/portfolios/<portfolio_id>/holdings/<symbol>")
def remove_holding(portfolio_id: str, symbol: str):
    return jsonify(_repository().remove_holding(portfolio_id, _path_symbol(symbol)))


@api.get("/api/v1/portfolios/<portfolio_id>/valuation")
def get_valuation(portfolio_id: str):
    return jsonify(_valuation().value(_repository().get(portfolio_id)))


@api.get("/api/v1/portfolios/<portfolio_id>/history")
def get_history(portfolio_id: str):
    limit = request.args.get("limit", DEFAULT_HISTORY_LIMIT, type=int)
    limit = max(1, min(limit, MAX_HISTORY_LIMIT))
    return jsonify(snapshots=_repository().list_snapshots(portfolio_id, limit))
