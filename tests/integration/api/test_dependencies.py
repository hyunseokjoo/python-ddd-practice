from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bootstrap.container import Container, RequestContainer
from app.domains.orders.domain.repository import OrderRepository
from app.main import create_app
from app.shared.database.connection import Settings


@contextmanager
def override_repository(
    container: Container, repository: OrderRepository
) -> Iterator[None]:
    def build_request_container() -> RequestContainer:
        scope = RequestContainer()
        scope.orders().order_repository.override(repository)
        return scope

    with container.request_container.override(
        providers.Callable(build_request_container)
    ):
        yield


def get_factory(client: TestClient) -> async_sessionmaker[AsyncSession]:
    async def resolve() -> async_sessionmaker[AsyncSession]:
        return await client.app.state.container.session_factory.async_()

    return client.portal.call(resolve)


def test_requests_use_separate_transaction_sessions(client: TestClient) -> None:
    container = client.app.state.container
    factory = get_factory(client)
    sessions: list[AsyncSession] = []

    def track_session() -> AsyncSession:
        session = factory()
        sessions.append(session)
        return session

    with container.session_factory.override(track_session):
        created = client.post("/orders")
        assert created.status_code == 201
        assert len(sessions) == 1
        loaded = client.get(f"/orders/{created.json()['order_id']}")
        assert loaded.status_code == 200
        assert len(sessions) == 2
        assert sessions[0] is not sessions[1]


def test_container_repository_override_is_used_by_api(client: TestClient) -> None:
    created = client.post("/orders")
    assert created.status_code == 201
    path = f"/orders/{created.json()['order_id']}"
    repository = Mock(spec=OrderRepository)
    repository.get.return_value = None
    with override_repository(client.app.state.container, repository):
        assert client.get(path).status_code == 404
    assert client.get(path).status_code == 200


def test_apps_keep_separate_containers(client: TestClient, database_url: str) -> None:
    with TestClient(create_app(Settings(database_url=database_url))) as other:
        created = client.post("/orders")
        assert created.status_code == 201
        path = f"/orders/{created.json()['order_id']}"
        repository = Mock(spec=OrderRepository)
        repository.get.return_value = None
        with override_repository(other.app.state.container, repository):
            assert other.get(path).status_code == 404
            assert client.get(path).status_code == 200
        assert other.get(path).status_code == 200
    assert client.get(path).status_code == 200


def test_commit_failure_rolls_back_and_closes_session(client: TestClient) -> None:
    container = client.app.state.container
    session = get_factory(client)()

    def fail_commit(session: object) -> None:
        raise RuntimeError("commit failed")

    event.listen(session.sync_session, "before_commit", fail_commit)
    with (
        patch.object(session, "close", wraps=session.close) as close,
        container.session_factory.override(lambda: session),
    ):
        with pytest.raises(RuntimeError, match="commit failed"):
            client.post("/orders")
        close.assert_awaited_once_with()
    assert not session.in_transaction()
    assert client.get("/orders").json() == []


def test_request_closes_session_after_success(client: TestClient) -> None:
    container = client.app.state.container
    session = get_factory(client)()
    with (
        patch.object(session, "close", wraps=session.close) as close,
        container.session_factory.override(lambda: session),
    ):
        assert client.post("/orders").status_code == 201
        close.assert_awaited_once_with()
