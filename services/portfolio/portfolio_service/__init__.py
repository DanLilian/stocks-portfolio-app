"""Portfolio microservice: manages holdings in MongoDB and values them using live quotes."""

from portfolio_service.app import create_app

__all__ = ["create_app"]
