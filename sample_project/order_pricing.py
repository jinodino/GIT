"""Calculate a checkout total from order items and a discount rate."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class OrderItem:
    name: str
    unit_price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("상품 이름은 비어 있을 수 없습니다.")
        if self.unit_price < 0:
            raise ValueError("상품 가격은 음수일 수 없습니다.")
        if self.quantity < 1:
            raise ValueError("수량은 1 이상이어야 합니다.")


def calculate_order_total(
    items: Sequence[OrderItem], discount_rate: Decimal = Decimal(0)
) -> Decimal:
    """Return the amount to charge after applying a fractional discount."""
    if not items:
        raise ValueError("주문에는 상품이 하나 이상 필요합니다.")
    if not Decimal(0) <= discount_rate < Decimal(1):
        raise ValueError("할인율은 0 이상 1 미만이어야 합니다.")

    subtotal = sum(
        (item.unit_price * item.quantity for item in items),
        start=Decimal(0),
    )
    total = subtotal * (Decimal(1) - discount_rate)
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
