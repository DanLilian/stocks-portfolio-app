"""End-to-end check against a running stack. Expects MARKET_DATA_PROVIDER=static.

Usage: python scripts/smoke_test.py
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid

MARKET_URL = os.getenv("MARKET_URL", "http://localhost:8001")
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "http://localhost:8002")
SNAPSHOT_WAIT_SECONDS = 30


def call(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(), error.code
    return status, json.loads(raw) if raw else {}


def main() -> None:
    status, quote = call("GET", f"{MARKET_URL}/api/v1/quotes/AAPL")
    assert status == 200 and quote["price"] == 190.0, quote
    print("market-data serves quotes")

    name = f"smoke-{uuid.uuid4().hex[:8]}"
    status, portfolio = call("POST", f"{PORTFOLIO_URL}/api/v1/portfolios", {"name": name})
    assert status == 201, portfolio
    portfolio_url = f"{PORTFOLIO_URL}/api/v1/portfolios/{portfolio['id']}"
    print("portfolio created in MongoDB")

    try:
        status, _ = call(
            "POST", f"{portfolio_url}/holdings", {"symbol": "AAPL", "quantity": 10, "price": 100}
        )
        assert status == 201
        status, _ = call("POST", f"{portfolio_url}/holdings", {"symbol": "MSFT", "quantity": 1, "price": 400})
        assert status == 201

        status, valuation = call("GET", f"{portfolio_url}/valuation")
        assert status == 200, valuation
        assert valuation["status"] == "complete", valuation
        assert valuation["totals"][0]["market_value"] == 2310.0, valuation
        assert valuation["totals"][0]["unrealized_pnl"] == 910.0, valuation
        print("portfolio service values holdings via market-data")

        deadline = time.monotonic() + SNAPSHOT_WAIT_SECONDS
        snapshots = []
        while not snapshots and time.monotonic() < deadline:
            time.sleep(1)
            _, history = call("GET", f"{portfolio_url}/history")
            snapshots = history["snapshots"]
        assert snapshots, "worker recorded no snapshot"
        print("worker records valuation history")
    finally:
        call("DELETE", portfolio_url)

    print("OK")


if __name__ == "__main__":
    main()
