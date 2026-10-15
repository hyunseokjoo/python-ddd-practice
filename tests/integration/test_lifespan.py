import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from app.main import create_app
from app.shared.database.connection import Settings, build_engine


def test_app_waits_for_async_resource_startup_and_shutdown(database_url: str) -> None:
    events: list[str] = []

    @asynccontextmanager
    async def resource() -> AsyncGenerator[None]:
        events.append("opened")
        try:
            yield
        finally:
            events.append("closed")

    app = create_app(Settings(database_url=database_url))
    app.state.container.async_resource = providers.Resource(resource)

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert events == ["opened"]
        assert events == ["opened", "closed"]

    asyncio.run(run_lifespan())


def test_app_cleans_up_resources_when_startup_fails(database_url: str) -> None:
    app = create_app(Settings(database_url=database_url))
    container = app.state.container
    events: list[str] = []

    @asynccontextmanager
    async def resource() -> AsyncGenerator[None]:
        events.append("opened")
        try:
            yield
        finally:
            events.append("closed")

    def fail_startup(dependency: None) -> None:
        raise RuntimeError("startup failed")

    container.async_resource = providers.Resource(resource)
    container.failing_resource = providers.Resource(
        fail_startup, dependency=container.async_resource
    )

    with pytest.raises(RuntimeError, match="startup failed"):
        with TestClient(app):
            pytest.fail("App must not start when resource initialization fails")

    assert events == ["opened", "closed"]
    assert not container.session_factory.initialized


def test_app_disposes_database_after_failure(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = build_engine(database_url)
    monkeypatch.setattr(
        "app.shared.database.connection.build_engine", lambda url: engine
    )
    try:
        with (
            patch.object(engine, "dispose", wraps=engine.dispose) as dispose,
            pytest.raises(RuntimeError, match="application failed"),
        ):
            with TestClient(create_app(Settings(database_url=database_url))):
                raise RuntimeError("application failed")
        dispose.assert_called_once_with()
    finally:
        engine.dispose()
