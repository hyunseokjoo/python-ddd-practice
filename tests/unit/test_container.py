from unittest.mock import patch

from sqlalchemy.orm import sessionmaker

from app.bootstrap.container import Container


def test_request_containers_share_sessions_internally_and_isolate_each_other() -> None:
    container = Container()
    with container.session_factory.override(sessionmaker()):
        first = container.request_container()
        second = container.request_container()
        try:
            first_session = first.session()
            second_session = second.session()
            assert first_session is not second_session
            assert first.orders().order_repository()._session is first_session
            assert first.unit_of_work()._session is first_session
            assert second.orders().order_repository()._session is second_session
            assert second.unit_of_work()._session is second_session

            with patch.object(
                first_session, "close", wraps=first_session.close
            ) as close:
                first.shutdown_resources()
                close.assert_called_once_with()
            assert second.session() is second_session
            assert second.session.initialized
        finally:
            first.shutdown_resources()
            second.shutdown_resources()
