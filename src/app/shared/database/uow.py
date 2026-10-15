from types import TracebackType
from typing import Protocol, Self

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError


class ConcurrentModification(Exception):
    pass


class UnitOfWork(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork:
    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Self:
        self._session.begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # 예외가 없어도 명시적으로 커밋하지 않은 변경은 남기지 않는다.
        self.rollback()
        if isinstance(exc_value, StaleDataError):
            raise ConcurrentModification(
                "다른 요청이 주문을 변경했습니다. 다시 조회해 주세요."
            ) from exc_value

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
