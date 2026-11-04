import logging
import os

from flask import Flask, jsonify
from pydantic import ValidationError
from pymongo.errors import PyMongoError
from werkzeug.exceptions import HTTPException

from portfolio_service.database import connect
from portfolio_service.errors import APIError
from portfolio_service.market_client import MarketDataClient
from portfolio_service.repository import PortfolioRepository
from portfolio_service.routes import api
from portfolio_service.valuation import ValuationService


def create_app(
    repository: PortfolioRepository | None = None,
    market_client: MarketDataClient | None = None,
) -> Flask:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    repository = repository or PortfolioRepository(connect())
    market_client = market_client or MarketDataClient.from_env()

    app = Flask(__name__)
    app.extensions["repository"] = repository
    app.extensions["valuation"] = ValuationService(market_client)
    app.register_blueprint(api)

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        details = [
            {"field": ".".join(str(part) for part in e["loc"]), "message": e["msg"]} for e in error.errors()
        ]
        body = {"error": {"code": "validation_error", "message": "Invalid request", "details": details}}
        return jsonify(body), 422

    @app.errorhandler(PyMongoError)
    def handle_database_error(error: PyMongoError):
        app.logger.error("Database error: %s", error)
        body = {"error": {"code": "database_unavailable", "message": "The database is unavailable"}}
        return jsonify(body), 503

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        body = {"error": {"code": error.name.lower().replace(" ", "_"), "message": error.description}}
        return jsonify(body), error.code

    return app
