import pytest
from pymongo.errors import PyMongoError


def test_create_and_get_portfolio(client):
    created = client.post("/api/v1/portfolios", json={"name": " Growth ", "description": "Long term"})

    assert created.status_code == 201
    assert created.json["name"] == "Growth"
    assert created.json["holdings"] == []
    assert created.headers["Location"] == f"/api/v1/portfolios/{created.json['id']}"

    fetched = client.get(f"/api/v1/portfolios/{created.json['id']}")
    assert fetched.json == created.json


def test_duplicate_name_conflicts(client):
    client.post("/api/v1/portfolios", json={"name": "Growth"})
    response = client.post("/api/v1/portfolios", json={"name": "Growth"})
    assert response.status_code == 409


def test_list_portfolios(client):
    client.post("/api/v1/portfolios", json={"name": "A"})
    client.post("/api/v1/portfolios", json={"name": "B"})
    names = [p["name"] for p in client.get("/api/v1/portfolios").json["portfolios"]]
    assert names == ["A", "B"]


def test_update_portfolio(client, portfolio_id):
    response = client.patch(f"/api/v1/portfolios/{portfolio_id}", json={"description": "Updated"})
    assert response.status_code == 200
    assert response.json["description"] == "Updated"
    assert response.json["name"] == "Retirement"


def test_rename_to_existing_name_conflicts(client, portfolio_id):
    client.post("/api/v1/portfolios", json={"name": "Other"})
    response = client.patch(f"/api/v1/portfolios/{portfolio_id}", json={"name": "Other"})
    assert response.status_code == 409


def test_delete_portfolio_also_removes_history(client, repository, portfolio_id):
    repository.add_snapshot(portfolio_id, [], "complete")

    assert client.delete(f"/api/v1/portfolios/{portfolio_id}").status_code == 204
    assert client.get(f"/api/v1/portfolios/{portfolio_id}").status_code == 404
    assert repository._snapshots.count_documents({}) == 0


@pytest.mark.parametrize("portfolio_id", ["not-an-id", "507f1f77bcf86cd799439011"])
def test_missing_portfolio_returns_404(client, portfolio_id):
    response = client.get(f"/api/v1/portfolios/{portfolio_id}")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "body",
    [{}, {"name": ""}, {"name": "x" * 101}, {"name": {"$ne": None}}, {"name": "x", "unexpected": 1}],
)
def test_invalid_portfolio_body_returns_422(client, body):
    response = client.post("/api/v1/portfolios", json=body)
    assert response.status_code == 422
    assert response.json["error"]["code"] == "validation_error"


def test_malformed_json_returns_400(client):
    response = client.post("/api/v1/portfolios", data="{oops", content_type="application/json")
    assert response.status_code == 400
    assert "error" in response.json


def test_health_reports_database_state(client, repository, monkeypatch):
    assert client.get("/health").json["database"] == "up"

    def fail():
        raise PyMongoError("down")

    monkeypatch.setattr(repository, "ping", fail)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json["database"] == "down"
