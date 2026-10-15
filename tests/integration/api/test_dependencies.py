from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bootstrap.container import Container, RequestContainer
from app.domains.orders.domain.repository import OrderRepository
from app.main import create_app
from app.shared.database.connection import Settings
from app.shared.database.uow import SqlAlchemyUnitOfWork


@contextmanager
def override_repository(
    container: Container, repository: OrderRepository
) -> Iterator[None]:
    def build_request_container() -> RequestContainer:
        scope = RequestContainer(session_factory=container.session_factory())
        scope.orders().order_repository.override(repository)
        return scope

    with container.request_container.override(
        providers.Callable(build_request_container)
    ):
        yield


def test_repository_and_uow_share_one_session_per_request(
    client: TestClient,
) -> None:
    container = client.app.state.container
    factory = container.session_factory()
    sessions: list[Session] = []

    def track_session() -> Session:
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


def test_container_uow_override_rolls_back_failed_request(client: TestClient) -> None:
    class FailingUnitOfWork(SqlAlchemyUnitOfWork):
        def commit(self) -> None:
            raise RuntimeError("commit failed")

    container = client.app.state.container
    session = container.session_factory()()

    def build_request_container() -> RequestContainer:
        scope = RequestContainer(session_factory=lambda: session)
        scope.unit_of_work.override(
            providers.Factory(FailingUnitOfWork, session=scope.session)
        )
        return scope

    with (
        patch.object(session, "close", wraps=session.close) as close,
        container.request_container.override(
            providers.Callable(build_request_container)
        ),
    ):
        with pytest.raises(RuntimeError, match="commit failed"):
            client.post("/orders")
        close.assert_called_once_with()

    assert client.get("/orders").json() == []


def test_request_closes_session_after_success(client: TestClient) -> None:
    container = client.app.state.container
    session = container.session_factory()()
    with (
        patch.object(session, "close", wraps=session.close) as close,
        container.session_factory.override(lambda: session),
    ):
        assert client.post("/orders").status_code == 201
        close.assert_called_once_with()
