from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app.bootstrap.container import (
    Container,
    RequestContainer,
    RequestContainerDependency,
)
from app.domains.orders.application.create_order import CreateOrderCommand
from app.domains.orders.application.get_order_by_id import GetOrderByIdQuery
from app.domains.orders.domain.repository import OrderRepository
from app.main import create_app
from app.shared.database.connection import Settings


@contextmanager
def override_repository(
    container: Container, repository: OrderRepository
) -> Iterator[None]:
    def build_request_container(session: AsyncSession) -> RequestContainer:
        scope = RequestContainer(session=session)
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


@pytest.mark.parametrize(
    ("failure", "status_code"),
    [(RuntimeError, 500), (StaleDataError, 409)],
)
def test_commit_failure_returns_error_before_response_and_rolls_back(
    database_url: str,
    failure: type[Exception],
    status_code: int,
) -> None:
    app = create_app(Settings(database_url=database_url))
    with TestClient(app, raise_server_exceptions=False) as client:
        container = app.state.container
        session = get_factory(client)()

        def fail_commit(session: object) -> None:
            raise failure("sensitive commit failure")

        event.listen(session.sync_session, "before_commit", fail_commit)
        with (
            patch.object(session, "close", wraps=session.close) as close,
            container.session_factory.override(lambda: session),
        ):
            response = client.post("/orders")
            assert response.status_code == status_code
            assert "sensitive commit failure" not in response.text
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


@pytest.mark.parametrize("detail", [False, True], ids=["list", "detail"])
def test_read_requests_finish_transaction_and_close_sessions(
    client: TestClient, detail: bool
) -> None:
    created = client.post("/orders")
    assert created.status_code == 201
    path = f"/orders/{created.json()['order_id']}" if detail else "/orders"
    container = client.app.state.container
    session = get_factory(client)()

    commits: list[object] = []
    event.listen(session.sync_session, "after_commit", commits.append)
    with (
        patch.object(session, "close", wraps=session.close) as close,
        container.session_factory.override(lambda: session),
    ):
        assert client.get(path).status_code == 200
        assert len(commits) == 1
        close.assert_awaited_once_with()
    assert not session.in_transaction()


@pytest.mark.parametrize(
    "fail_second", [False, True], ids=["commit_once", "rollback_all"]
)
def test_multiple_use_cases_share_one_request_transaction(
    database_url: str,
    fail_second: bool,
) -> None:
    first_id, second_id = uuid4(), uuid4()
    app = create_app(Settings(database_url=database_url))
    commits: list[object] = []

    @app.post("/batch")
    async def batch(container: RequestContainerDependency) -> dict[str, bool]:
        await container.orders().create_order(CreateOrderCommand(order_id=first_id))
        # 같은 세션의 조회 후 다음 변경도 별도 begin 없이 참여한다.
        order = await container.orders().get_order_by_id(
            GetOrderByIdQuery(order_id=first_id)
        )
        assert order.id == first_id
        await container.orders().create_order(
            CreateOrderCommand(order_id=first_id if fail_second else second_id)
        )
        assert commits == []
        return {"created": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        session = get_factory(client)()
        event.listen(session.sync_session, "after_commit", commits.append)
        with (
            patch.object(session, "close", wraps=session.close) as close,
            app.state.container.session_factory.override(lambda: session),
        ):
            response = client.post("/batch")
            assert response.status_code == (500 if fail_second else 200)
            assert len(commits) == (0 if fail_second else 1)
            close.assert_awaited_once_with()
        assert not session.in_transaction()
        expected = 404 if fail_second else 200
        assert client.get(f"/orders/{first_id}").status_code == expected
        assert client.get(f"/orders/{second_id}").status_code == expected
