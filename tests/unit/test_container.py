from app.bootstrap.container import Container


def test_request_containers_have_separate_overrides() -> None:
    container = Container()
    first = container.request_container()
    second = container.request_container()
    repository = object()
    with first.orders().order_repository.override(repository):
        assert first.orders().order_repository() is repository
        assert second.orders().order_repository() is not repository
    assert first.orders().order_repository() is not repository
