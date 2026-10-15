from dependency_injector import containers, providers
from sqlalchemy.orm import Session

from app.domains.orders.application.add_product_to_order import add_product_to_order
from app.domains.orders.application.cancel_order import cancel_order
from app.domains.orders.application.confirm_order import confirm_order
from app.domains.orders.application.create_order import create_order
from app.domains.orders.application.get_order_by_id import get_order_by_id
from app.domains.orders.application.list_orders_by_status import list_orders_by_status
from app.domains.orders.infrastructure.order_repository import SqlAlchemyOrderRepository
from app.shared.database.uow import UnitOfWork


class OrdersContainer(containers.DeclarativeContainer):
    session = providers.Dependency(instance_of=Session)
    unit_of_work = providers.Dependency[UnitOfWork]()
    order_repository = providers.Factory(SqlAlchemyOrderRepository, session=session)

    create_order = providers.Callable(
        create_order, orders=order_repository, uow=unit_of_work
    )
    add_product_to_order = providers.Callable(
        add_product_to_order, orders=order_repository, uow=unit_of_work
    )
    confirm_order = providers.Callable(
        confirm_order, orders=order_repository, uow=unit_of_work
    )
    cancel_order = providers.Callable(
        cancel_order, orders=order_repository, uow=unit_of_work
    )
    get_order_by_id = providers.Callable(get_order_by_id, orders=order_repository)
    list_orders_by_status = providers.Callable(
        list_orders_by_status, orders=order_repository
    )
