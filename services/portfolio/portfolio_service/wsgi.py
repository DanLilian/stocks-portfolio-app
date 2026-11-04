"""Gunicorn entry point. Creates indexes once at startup, then serves the app."""

from portfolio_service.app import create_app
from portfolio_service.database import connect
from portfolio_service.repository import PortfolioRepository

repository = PortfolioRepository(connect())
repository.ensure_indexes()

app = create_app(repository=repository)
