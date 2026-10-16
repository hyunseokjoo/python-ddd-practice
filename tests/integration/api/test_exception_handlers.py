import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm.exc import StaleDataError

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.exceptions import OrderRuleViolation
from app.domains.orders.presentation.exception_handlers import (
    register_exception_handlers,
)


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (OrderNotFound("internal-order-id"), 404, "주문을 찾을 수 없습니다."),
        (
            OrderRuleViolation("상품이 없는 주문은 확정할 수 없습니다."),
            409,
            "상품이 없는 주문은 확정할 수 없습니다.",
        ),
        (
            StaleDataError("sensitive SQL parameters"),
            409,
            "다른 요청이 주문을 변경했습니다. 다시 조회해 주세요.",
        ),
    ],
)
def test_order_exceptions_become_http_responses(
    error: Exception, status_code: int, detail: str
) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/error")
    async def fail() -> None:
        raise error

    with TestClient(app) as client:
        response = client.get("/error")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
