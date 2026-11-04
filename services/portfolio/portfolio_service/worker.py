"""Background worker that records a valuation snapshot of every portfolio on an interval."""

import logging
import os
import threading

from pymongo.errors import PyMongoError

from portfolio_service.database import connect
from portfolio_service.errors import APIError
from portfolio_service.market_client import MarketDataClient
from portfolio_service.repository import PortfolioRepository
from portfolio_service.valuation import ValuationService

logger = logging.getLogger("portfolio_service.worker")


def snapshot_all(repository: PortfolioRepository, valuation: ValuationService) -> int:
    """Snapshot each portfolio that has at least one priced position; return how many were saved."""
    saved = 0
    for portfolio in repository.list_all():
        if not portfolio["holdings"]:
            continue
        try:
            result = valuation.value(portfolio)
        except APIError as exc:
            logger.warning("Skipping snapshot of %s: %s", portfolio["id"], exc.message)
            continue
        if not result["totals"]:
            logger.warning("Skipping snapshot of %s: no quotes available", portfolio["id"])
            continue
        repository.add_snapshot(portfolio["id"], result["totals"], result["status"])
        saved += 1
    return saved


def run(stop: threading.Event | None = None) -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    interval = float(os.getenv("SNAPSHOT_INTERVAL_SECONDS", "300"))
    stop = stop or threading.Event()

    repository = PortfolioRepository(connect())
    valuation = ValuationService(MarketDataClient.from_env())

    logger.info("Recording valuation snapshots every %s seconds", interval)
    while not stop.is_set():
        try:
            logger.info("Saved %d snapshots", snapshot_all(repository, valuation))
        except PyMongoError as exc:
            logger.warning("Snapshot run failed: %s", exc)
        stop.wait(interval)


if __name__ == "__main__":
    run()
