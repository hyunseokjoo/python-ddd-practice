import os
from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy_transactional.asyncio import sessionmaker_context

from app.shared.database.connection import Settings, build_engine, open_database


@pytest.fixture
def database_url() -> Iterator[str]:
    url = make_url(
        Settings(
            database_url=os.environ.get(
                "TEST_DATABASE_URL",
                "postgresql+psycopg://orders:password@localhost:5432/orders",
            )
        ).database_url
    )
    schema = f"test_{uuid4().hex}"
    engine = build_engine(url.render_as_string(hide_password=False))
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        try:
            if url.get_backend_name() == "mysql":
                test_url = url.set(database=schema).render_as_string(
                    hide_password=False
                )
            else:
                test_url = url.update_query_dict(
                    {"options": f"-csearch_path={schema}"}
                ).render_as_string(hide_password=False)
            config = Config("alembic.ini")
            config.attributes["database_url"] = test_url
            command.upgrade(config, "head")
            yield test_url
        finally:
            with engine.begin() as connection:
                connection.execute(
                    DropSchema(schema, cascade=url.get_backend_name() == "postgresql")
                )
    finally:
        engine.dispose()


@pytest.fixture
async def sessions(
    database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with open_database(database_url) as session_factory:
        async with sessionmaker_context(session_factory):
            yield session_factory
