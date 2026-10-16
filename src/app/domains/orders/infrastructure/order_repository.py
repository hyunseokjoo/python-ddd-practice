import builtins
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy_transactional.asyncio import current_session

from app.domains.orders.domain.order import Order
from app.domains.orders.domain.order_line import OrderLine
from app.domains.orders.infrastructure.persistence.order import OrderRow
from app.domains.orders.infrastructure.persistence.order_line import OrderLineRow


class SqlAlchemyOrderRepository:
    async def get(self, order_id: UUID) -> Order | None:
        row = await current_session().get(OrderRow, str(order_id))
        if row is None:
            return None
        return (await self._restore_orders([row]))[0]

    async def list(
        self, status: Order.Status | None, limit: int, offset: int
    ) -> list[Order]:
        statement = select(OrderRow).order_by(OrderRow.id).limit(limit).offset(offset)
        if status is not None:
            statement = statement.where(OrderRow.status == status.value)
        return await self._restore_orders(
            (await current_session().scalars(statement)).all()
        )

    async def _restore_orders(self, rows: Sequence[OrderRow]) -> builtins.list[Order]:
        if not rows:
            return []
        lines_by_order: dict[str, list[OrderLine]] = {row.id: [] for row in rows}
        lines = await current_session().scalars(
            select(OrderLineRow)
            .where(OrderLineRow.order_id.in_(lines_by_order))
            .order_by(OrderLineRow.position)
        )
        for line in lines:
            lines_by_order[line.order_id].append(
                OrderLine(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price_won=line.unit_price_won,
                )
            )
        orders = []
        for row in rows:
            order_id = UUID(row.id)
            orders.append(
                Order(
                    order_id,
                    tuple(lines_by_order[row.id]),
                    Order.Status(row.status),
                    version=row.version,
                )
            )
        return orders

    async def add(self, order: Order) -> None:
        row = OrderRow(id=str(order.id), status=order.status.value, version=1)
        current_session().add(row)
        await current_session().flush()
        self._write_lines(order)

    async def save(self, order: Order) -> None:
        row = await current_session().get(OrderRow, str(order.id))
        if row is None or row.version != order.version:
            raise StaleDataError("Order version has changed")
        row.status = order.status.value
        # 항목만 변경해도 주문 버전을 갱신해 동시 수정을 감지한다.
        row.version += 1
        # 항목 저장 실패 시 주문 변경도 롤백해야 하므로 커밋 대신 flush만 한다.
        await current_session().flush()
        await current_session().execute(
            delete(OrderLineRow).where(OrderLineRow.order_id == str(order.id))
        )
        self._write_lines(order)

    def _write_lines(self, order: Order) -> None:
        current_session().add_all(
            OrderLineRow(
                order_id=str(order.id),
                position=position,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price_won=line.unit_price_won,
            )
            for position, line in enumerate(order.lines)
        )
