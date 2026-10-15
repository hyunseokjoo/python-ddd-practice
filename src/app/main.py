from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from dependency_injector.ext.starlette import Lifespan
from fastapi import FastAPI

from app.bootstrap.container import Container
from app.bootstrap.logging import configure_logging
from app.domains.orders.presentation.exception_handlers import (
    register_exception_handlers,
)
from app.domains.orders.presentation.router import router
from app.shared.database.connection import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    configuration = settings or Settings()
    container = Container()
    container.config.from_pydantic(configuration)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        lifecycle = Lifespan(container)
        async with AsyncExitStack() as cleanup:
            # 초기화 도중 실패해도 이미 열린 자원을 정리한다.
            cleanup.push_async_exit(lifecycle)
            await lifecycle.__aenter__()
            yield

    app = FastAPI(title="Orders · DDD & CQRS", version="0.1.0", lifespan=lifespan)
    app.state.container = container
    register_exception_handlers(app)
    app.include_router(router)

    return app
