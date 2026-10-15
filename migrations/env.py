from alembic import context

from app.domains.orders.infrastructure.persistence.order import OrderRow
from app.domains.orders.infrastructure.persistence.order_line import OrderLineRow
from app.shared.database.base import Base
from app.shared.database.connection import Settings, build_engine

target_metadata = Base.metadata
assert {OrderRow.__table__, OrderLineRow.__table__}.issubset(
    set(target_metadata.tables.values())
)


def run_migrations() -> None:
    url = context.config.attributes.get("database_url") or Settings().database_url
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
