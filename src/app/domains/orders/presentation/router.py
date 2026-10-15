from fastapi import APIRouter

from app.domains.orders.presentation import (
    add_product_to_order,
    cancel_order,
    confirm_order,
    create_order,
    get_order_by_id,
    list_orders_by_status,
)

router = APIRouter(tags=["orders"])
for module in (
    create_order,
    add_product_to_order,
    confirm_order,
    cancel_order,
    get_order_by_id,
    list_orders_by_status,
):
    router.include_router(module.router, prefix="/orders")
