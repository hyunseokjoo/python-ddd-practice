from collections.abc import AsyncIterator
from typing import Annotated, cast

from dependency_injector import containers, providers
from fastapi import Depends, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.orders.container import OrdersContainer
from app.shared.database.connection import open_database


class RequestContainer(containers.DeclarativeContainer):
    session = providers.Dependency(instance_of=AsyncSession)
    orders = providers.Container(OrdersContainer, session=session)


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    session_factory = providers.Resource[async_sessionmaker[AsyncSession]](
        open_database, database_url=config.database_url
    )
    request_container = providers.Factory(RequestContainer)


async def get_request_container(request: Request) -> AsyncIterator[RequestContainer]:
    container = cast(Container, request.app.state.container)
    factory = await container.session_factory.async_()
    with logger.catch(
        reraise=True, message="요청 트랜잭션 실패: {record[exception].type.__name__}"
    ):
        async with factory() as session, session.begin():
            yield container.request_container(session=session)


# 커밋 실패를 성공 응답 전송 전에 처리한다.
RequestContainerDependency = Annotated[
    RequestContainer, Depends(get_request_container, scope="function")
]
