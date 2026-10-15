from collections.abc import Generator
from contextlib import contextmanager

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://orders:password@localhost:5432/orders",
        pattern=r"^(postgresql\+psycopg|mysql\+pymysql)://",
    )


def build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


@contextmanager
def open_database(database_url: str) -> Generator[sessionmaker[Session]]:
    engine = build_engine(database_url)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()
