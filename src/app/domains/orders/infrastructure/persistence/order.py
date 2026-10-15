from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class OrderRow(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')"),
        CheckConstraint("version > 0"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}
