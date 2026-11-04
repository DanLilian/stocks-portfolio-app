from flask import Blueprint, current_app, jsonify, request

from market_data.errors import APIError, InvalidSymbol
from market_data.models import normalize_symbol
from market_data.quote_service import QuoteService

api = Blueprint("api", __name__)

MAX_SYMBOLS_PER_REQUEST = 50


def _quote_service() -> QuoteService:
    return current_app.extensions["quote_service"]


@api.get("/health")
def health():
    return jsonify(status="ok", service="market-data")


@api.get("/api/v1/quotes/<symbol>")
def get_quote(symbol: str):
    return jsonify(_quote_service().get_quote(normalize_symbol(symbol)))


@api.get("/api/v1/quotes")
def get_quotes():
    raw_symbols = [s for s in request.args.get("symbols", "").split(",") if s.strip()]
    if not raw_symbols:
        raise InvalidSymbol("Provide a comma-separated 'symbols' query parameter")
    if len(raw_symbols) > MAX_SYMBOLS_PER_REQUEST:
        raise InvalidSymbol(f"A request can ask for at most {MAX_SYMBOLS_PER_REQUEST} symbols")

    valid, errors = [], {}
    for raw in raw_symbols:
        try:
            valid.append(normalize_symbol(raw))
        except APIError as exc:
            errors[raw.strip()] = {"code": exc.code, "message": exc.message}

    quotes, lookup_errors = _quote_service().get_quotes(valid)
    return jsonify(quotes=quotes, errors={**errors, **lookup_errors})
