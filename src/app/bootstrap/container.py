from collections.abc import AsyncIterator
from typing import Annotated, cast

from dependency_injector import containers, providers
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy_transactional.asyncio import sessionmaker_context

from app.domains.orders.container import OrdersContainer
from app.shared.database.connection import open_database


class RequestContainer(containers.DeclarativeContainer):
    orders = providers.Container(OrdersContainer)


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    session_factory = providers.Resource[async_sessionmaker[AsyncSession]](
        open_database, database_url=config.database_url
    )
    request_container = providers.Factory(RequestContainer)


async def get_request_container(request: Request) -> AsyncIterator[RequestContainer]:
    container = cast(Container, request.app.state.container)
    factory = await container.session_factory.async_()
    async with sessionmaker_context(factory):
        yield container.request_container()


RequestContainerDependency = Annotated[RequestContainer, Depends(get_request_container)]
