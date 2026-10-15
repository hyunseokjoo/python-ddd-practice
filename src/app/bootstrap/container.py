from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from typing import Annotated, cast

from dependency_injector import containers, providers
from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.domains.orders.container import OrdersContainer
from app.shared.database.connection import open_database
from app.shared.database.uow import SqlAlchemyUnitOfWork


@contextmanager
def open_session(session_factory: Callable[[], Session]) -> Generator[Session]:
    with session_factory() as session:
        yield session


class RequestContainer(containers.DeclarativeContainer):
    session_factory = providers.Dependency[Callable[[], Session]]()
    session = providers.Resource(open_session, session_factory=session_factory)
    unit_of_work = providers.Factory(SqlAlchemyUnitOfWork, session=session)
    orders = providers.Container(
        OrdersContainer, session=session, unit_of_work=unit_of_work
    )


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    session_factory = providers.Resource[sessionmaker[Session]](
        open_database,
        database_url=config.database_url,
    )
    request_container = providers.Factory(
        RequestContainer, session_factory=session_factory
    )


def get_request_container(request: Request) -> Iterator[RequestContainer]:
    container = cast(Container, request.app.state.container).request_container()
    try:
        yield container
    finally:
        container.shutdown_resources()


RequestContainerDependency = Annotated[RequestContainer, Depends(get_request_container)]
