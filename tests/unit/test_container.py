from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.container import Container


def test_request_containers_share_injected_session_and_isolate_overrides() -> None:
    container = Container()
    first_session = AsyncSession()
    second_session = AsyncSession()
    first = container.request_container(session=first_session)
    second = container.request_container(session=second_session)
    assert first.orders().order_repository()._session is first_session
    assert first.orders().order_repository()._session is first_session
    assert second.orders().order_repository()._session is second_session

    repository = object()
    with first.orders().order_repository.override(repository):
        assert first.orders().order_repository() is repository
        assert second.orders().order_repository() is not repository
    assert first.orders().order_repository() is not repository
