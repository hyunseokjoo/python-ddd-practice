from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://orders:password@localhost:5432/orders",
        pattern=r"^(postgresql\+psycopg|mysql\+pymysql)://",
    )


def build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


@asynccontextmanager
async def open_database(
    database_url: str,
) -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    url = make_url(database_url)
    # 환경 설정은 마이그레이션과 공유하고, 요청 처리에는 비동기 드라이버를 쓴다.
    if url.drivername == "mysql+pymysql":
        url = url.set(drivername="mysql+aiomysql")
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
