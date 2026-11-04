import logging
import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from market_data.errors import APIError
from market_data.providers import build_provider
from market_data.quote_service import QuoteService
from market_data.routes import api


def create_app(quote_service: QuoteService | None = None) -> Flask:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = Flask(__name__)
    app.extensions["quote_service"] = quote_service or QuoteService(
        provider=build_provider(os.getenv("MARKET_DATA_PROVIDER", "yahoo")),
        ttl_seconds=float(os.getenv("QUOTE_TTL_SECONDS", "30")),
    )
    app.register_blueprint(api)

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        body = {"error": {"code": error.name.lower().replace(" ", "_"), "message": error.description}}
        return jsonify(body), error.code

    return app
