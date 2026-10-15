"""Orders and order lines."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')"),
        sa.CheckConstraint("version > 0"),
    )
    op.create_table(
        "order_lines",
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_won", sa.Integer(), nullable=False),
        sa.UniqueConstraint("order_id", "product_id"),
        sa.CheckConstraint("quantity > 0 AND quantity <= 10000"),
        sa.CheckConstraint("unit_price_won >= 0 AND unit_price_won <= 1000000000"),
    )


def downgrade() -> None:
    op.drop_table("order_lines")
    op.drop_table("orders")
