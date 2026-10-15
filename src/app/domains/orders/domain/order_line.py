from pydantic import BaseModel, ConfigDict, Field


class OrderLine(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", revalidate_instances="always"
    )

    product_id: str = Field(min_length=1, max_length=100, pattern=r"\S")
    quantity: int = Field(gt=0, le=10000, strict=True)
    unit_price_won: int = Field(ge=0, le=1_000_000_000, strict=True)

    @property
    def subtotal(self) -> int:
        return self.quantity * self.unit_price_won
