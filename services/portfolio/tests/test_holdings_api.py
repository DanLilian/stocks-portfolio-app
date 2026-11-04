import pytest


def holdings_url(portfolio_id, suffix=""):
    return f"/api/v1/portfolios/{portfolio_id}/holdings{suffix}"


def test_buy_adds_holding(client, portfolio_id):
    response = client.post(holdings_url(portfolio_id), json={"symbol": "aapl", "quantity": 10, "price": 100})

    assert response.status_code == 201
    assert response.json["holdings"] == [{"symbol": "AAPL", "quantity": 10, "average_cost": 100}]


def test_second_buy_uses_weighted_average_cost(client, portfolio_id):
    client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 10, "price": 100})
    response = client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 30, "price": 200})

    assert response.json["holdings"] == [{"symbol": "AAPL", "quantity": 40, "average_cost": 175}]


def test_partial_sell_keeps_average_cost(client, portfolio_id):
    client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 10, "price": 100})
    response = client.post(holdings_url(portfolio_id, "/AAPL/sell"), json={"quantity": 4})

    assert response.status_code == 200
    assert response.json["holdings"] == [{"symbol": "AAPL", "quantity": 6, "average_cost": 100}]


def test_selling_everything_removes_holding(client, portfolio_id):
    client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 0.3, "price": 100})
    client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 0.6, "price": 100})
    response = client.post(holdings_url(portfolio_id, "/AAPL/sell"), json={"quantity": 0.9})

    assert response.json["holdings"] == []


def test_cannot_sell_more_than_held(client, portfolio_id):
    client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 1, "price": 100})
    response = client.post(holdings_url(portfolio_id, "/AAPL/sell"), json={"quantity": 2})

    assert response.status_code == 409
    assert client.get(f"/api/v1/portfolios/{portfolio_id}").json["holdings"][0]["quantity"] == 1


def test_selling_unknown_holding_returns_404(client, portfolio_id):
    assert client.post(holdings_url(portfolio_id, "/AAPL/sell"), json={"quantity": 1}).status_code == 404


def test_set_holding_replaces_values(client, portfolio_id):
    client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 1, "price": 100})
    response = client.put(holdings_url(portfolio_id, "/aapl"), json={"quantity": 5, "average_cost": 50})

    assert response.json["holdings"] == [{"symbol": "AAPL", "quantity": 5, "average_cost": 50}]


def test_remove_holding(client, portfolio_id):
    client.post(holdings_url(portfolio_id), json={"symbol": "AAPL", "quantity": 1, "price": 100})
    client.post(holdings_url(portfolio_id), json={"symbol": "MSFT", "quantity": 1, "price": 100})

    response = client.delete(holdings_url(portfolio_id, "/AAPL"))

    assert [h["symbol"] for h in response.json["holdings"]] == ["MSFT"]


def test_symbols_with_special_characters_are_supported(client, portfolio_id):
    client.post(holdings_url(portfolio_id), json={"symbol": "BRK-B", "quantity": 1, "price": 1})
    client.post(holdings_url(portfolio_id), json={"symbol": "VOD.L", "quantity": 1, "price": 1})
    response = client.delete(holdings_url(portfolio_id, "/VOD.L"))
    assert [h["symbol"] for h in response.json["holdings"]] == ["BRK-B"]


@pytest.mark.parametrize(
    "body",
    [
        {"symbol": "AAPL", "quantity": 0, "price": 1},
        {"symbol": "AAPL", "quantity": -1, "price": 1},
        {"symbol": "AAPL", "quantity": 1, "price": -1},
        {"symbol": "AAPL", "quantity": "1", "price": 1},
        {"symbol": "AAPL", "quantity": True, "price": 1},
        {"symbol": "AAPL", "quantity": 1},
        {"symbol": "not valid!", "quantity": 1, "price": 1},
        {"symbol": {"$gt": ""}, "quantity": 1, "price": 1},
    ],
)
def test_invalid_buy_returns_422(client, portfolio_id, body):
    assert client.post(holdings_url(portfolio_id), json=body).status_code == 422


def test_non_finite_numbers_are_rejected(client, portfolio_id):
    response = client.post(
        holdings_url(portfolio_id),
        data='{"symbol": "AAPL", "quantity": NaN, "price": 1}',
        content_type="application/json",
    )
    assert response.status_code == 422


def test_buy_on_missing_portfolio_returns_404(client):
    response = client.post(
        holdings_url("507f1f77bcf86cd799439011"), json={"symbol": "A", "quantity": 1, "price": 1}
    )
    assert response.status_code == 404


def test_write_conflict_is_retried(repository, portfolio_id):
    """A concurrent change between the read and the write must not be lost."""
    collection = repository._portfolios
    original = collection.find_one_and_update
    raced = []

    def racing_update(query, update, **kwargs):
        if not raced:
            raced.append(True)
            original(
                {"_id": query["_id"]},
                {
                    "$push": {"holdings": {"symbol": "MSFT", "quantity": 1, "average_cost": 1}},
                    "$inc": {"version": 1},
                },
            )
        return original(query, update, **kwargs)

    collection.find_one_and_update = racing_update

    portfolio = repository.buy(portfolio_id, "AAPL", 1, 1)

    assert {h["symbol"] for h in portfolio["holdings"]} == {"AAPL", "MSFT"}
