from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.orders.application.add_product_to_order import add_product_to_order
from app.domains.orders.application.cancel_order import cancel_order
from app.domains.orders.application.confirm_order import confirm_order
from app.domains.orders.application.create_order import create_order
from app.domains.orders.application.get_order_by_id import get_order_by_id
from app.domains.orders.application.list_orders_by_status import list_orders_by_status
from app.domains.orders.infrastructure.order_repository import SqlAlchemyOrderRepository


class OrdersContainer(containers.DeclarativeContainer):
    session = providers.Dependency(instance_of=AsyncSession)
    order_repository = providers.Factory(SqlAlchemyOrderRepository, session=session)

    create_order = providers.Callable(create_order, orders=order_repository)
    add_product_to_order = providers.Callable(
        add_product_to_order, orders=order_repository
    )
    confirm_order = providers.Callable(confirm_order, orders=order_repository)
    cancel_order = providers.Callable(cancel_order, orders=order_repository)
    get_order_by_id = providers.Callable(get_order_by_id, orders=order_repository)
    list_orders_by_status = providers.Callable(
        list_orders_by_status, orders=order_repository
    )
