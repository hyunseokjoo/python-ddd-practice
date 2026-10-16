from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.domains.orders.domain.order import Order
from app.domains.orders.domain.repository import OrderRepository


class ListOrdersByStatusQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Order.Status | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


@logger.catch(
    reraise=True,
    message=(
        "작업 실패: {record[exception].type.__name__} use_case=list_orders_by_status"
    ),
)
async def list_orders_by_status(
    query: ListOrdersByStatusQuery,
    orders: OrderRepository,
) -> list[Order]:
    orders_found = await orders.list(query.status, query.limit, query.offset)
    logger.info("주문 목록 조회 처리 count={}", len(orders_found))
    return orders_found
