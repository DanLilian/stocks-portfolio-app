"""Market data microservice: live stock quotes behind a small REST API."""

from market_data.app import create_app

__all__ = ["create_app"]
