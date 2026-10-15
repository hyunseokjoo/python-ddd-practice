from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class OrderLineRow(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "product_id"),
        CheckConstraint("quantity > 0 AND quantity <= 10000"),
        CheckConstraint("unit_price_won >= 0 AND unit_price_won <= 1000000000"),
    )

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int]
    unit_price_won: Mapped[int]
