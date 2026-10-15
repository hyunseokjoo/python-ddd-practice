from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def create_order(client: TestClient) -> str:
    response = client.post("/orders")
    assert response.status_code == 201
    order_id = response.json()["order_id"]
    assert response.headers["Location"] == f"/orders/{order_id}"
    return order_id


def test_order_lifecycle(client: TestClient) -> None:
    order_id = create_order(client)
    path = f"/orders/{order_id}"
    assert (
        client.post(
            f"{path}/lines",
            json={"product_id": "book", "quantity": 2, "unit_price_won": 12000},
        ).status_code
        == 204
    )
    assert client.get(path).json()["total_won"] == 24000
    assert client.post(f"{path}/confirm").status_code == 204
    summaries = client.get("/orders", params={"status": "confirmed"}).json()
    assert len(summaries) == 1
    assert summaries[0]["order_id"] == order_id
    assert summaries[0]["total_won"] == 24000
    assert summaries[0]["item_count"] == 1
    assert "lines" not in summaries[0]
    assert client.post(f"{path}/cancel").status_code == 204
    assert client.get(path).json()["status"] == "cancelled"
    assert client.get("/orders?status=confirmed").json() == []


def test_empty_order_confirmation_returns_409(client: TestClient) -> None:
    order_id = create_order(client)

    assert client.post(f"/orders/{order_id}/confirm").status_code == 409
    assert client.get(f"/orders/{order_id}").json()["status"] == "draft"


def test_confirmed_order_rejects_changes(client: TestClient) -> None:
    order_id = create_order(client)
    path = f"/orders/{order_id}"
    line = {"product_id": "book", "quantity": 2, "unit_price_won": 12000}
    assert client.post(f"{path}/lines", json=line).status_code == 204
    assert client.post(f"{path}/confirm").status_code == 204
    before = client.get(path).json()

    assert client.post(f"{path}/confirm").status_code == 409
    assert (
        client.post(
            f"{path}/lines",
            json={"product_id": "pen", "quantity": 1, "unit_price_won": 1000},
        ).status_code
        == 409
    )
    assert client.get(path).json() == before


@pytest.mark.parametrize(
    "body",
    [
        {"product_id": "book", "quantity": 0, "unit_price_won": 1},
        {"product_id": "book", "quantity": True, "unit_price_won": 1},
        {"product_id": "book", "quantity": "2", "unit_price_won": 1},
        {"product_id": "book", "quantity": 1, "unit_price_won": -1},
        {"product_id": " ", "quantity": 1, "unit_price_won": 1},
        {"product_id": "book", "quantity": 1, "unit_price_won": 1, "extra": 1},
    ],
)
def test_invalid_input_does_not_change_order(client: TestClient, body: dict) -> None:
    order_id = create_order(client)
    path = f"/orders/{order_id}"
    assert client.post(f"{path}/lines", json=body).status_code == 422
    assert client.get(path).json()["lines"] == []


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("POST", "/confirm", None),
        ("POST", "/cancel", None),
        ("POST", "/lines", {"product_id": "book", "quantity": 1, "unit_price_won": 1}),
    ],
    ids=["get", "confirm", "cancel", "add_product"],
)
def test_missing_order_returns_404(
    client: TestClient, method: str, suffix: str, body: dict | None
) -> None:
    path = f"/orders/{uuid4()}{suffix}"
    response = client.request(method, path, json=body)
    assert response.status_code == 404


def test_pagination(client: TestClient) -> None:
    for _ in range(3):
        create_order(client)
    all_orders = client.get("/orders").json()
    assert client.get("/orders?limit=1&offset=1").json() == all_orders[1:2]


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "offset=-1", "status=invalid"]
)
def test_invalid_query_returns_422(client: TestClient, query: str) -> None:
    assert client.get(f"/orders?{query}").status_code == 422


def test_queries_preserve_order_details_and_summaries(client: TestClient) -> None:
    order_ids = sorted(create_order(client) for _ in range(3))
    lines = [
        {"product_id": "pen", "quantity": 3, "unit_price_won": 1000},
        {"product_id": "book", "quantity": 2, "unit_price_won": 12000},
    ]
    for order_id in order_ids[1:]:
        for line in lines:
            assert (
                client.post(f"/orders/{order_id}/lines", json=line).status_code == 204
            )
        assert client.post(f"/orders/{order_id}/confirm").status_code == 204

    empty_summary = {
        "order_id": order_ids[0],
        "status": "draft",
        "total_won": 0,
        "item_count": 0,
        "version": 1,
    }
    summaries = client.get("/orders").json()
    assert summaries == [
        empty_summary,
        *[
            {
                "order_id": order_id,
                "status": "confirmed",
                "total_won": 27000,
                "item_count": 2,
                "version": 4,
            }
            for order_id in order_ids[1:]
        ],
    ]
    assert client.get(f"/orders/{order_ids[0]}").json() == {
        **empty_summary,
        "lines": [],
    }
    for summary in summaries[1:]:
        assert client.get(f"/orders/{summary['order_id']}").json() == {
            **summary,
            "lines": lines,
        }
    assert (
        client.get("/orders?status=confirmed&limit=1&offset=1").json() == summaries[2:]
    )
    assert client.get("/orders?status=confirmed&offset=2").json() == []


def test_openapi_documents_all_use_cases(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "post" in schema["paths"]["/orders"]
    assert "get" in schema["paths"]["/orders"]
    assert "post" in schema["paths"]["/orders/{order_id}/confirm"]
    assert "post" in schema["paths"]["/orders/{order_id}/cancel"]
    assert "post" in schema["paths"]["/orders/{order_id}/lines"]
    assert "get" in schema["paths"]["/orders/{order_id}"]
