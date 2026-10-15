from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domains.orders.application.exceptions import OrderNotFound
from app.domains.orders.domain.exceptions import OrderRuleViolation
from app.shared.database.uow import ConcurrentModification


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(OrderNotFound)
    async def not_found(request: Request, exc: OrderNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": "주문을 찾을 수 없습니다."}
        )

    @app.exception_handler(OrderRuleViolation)
    async def rule_violation(request: Request, exc: OrderRuleViolation) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ConcurrentModification)
    async def concurrent_change(
        request: Request, exc: ConcurrentModification
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
