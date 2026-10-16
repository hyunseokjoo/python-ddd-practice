from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy_transactional.asyncio import sessionmaker_context


@pytest.fixture
async def transaction_context() -> AsyncIterator[None]:
    # 저장소 대역만 사용하는 유스케이스는 DB 연결 없이 트랜잭션 경계를 실행한다.
    async with sessionmaker_context(async_sessionmaker()):
        yield
