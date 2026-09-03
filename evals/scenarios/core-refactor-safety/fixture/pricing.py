"""Pricing helpers with duplicated discount logic."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def price_checkout_line(unit_cents: int, qty: int, customer_tier: str) -> int:
    subtotal = Decimal(unit_cents) * qty
    if customer_tier == "gold":
        subtotal *= Decimal("0.92")
    elif customer_tier == "silver":
        subtotal *= Decimal("0.95")
    # callers rely on HALF_UP to cents
    return int(subtotal.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def price_invoice_line(unit_cents: int, qty: int, customer_tier: str, ship_cents: int) -> dict:
    goods = Decimal(unit_cents) * qty
    if customer_tier == "gold":
        goods *= Decimal("0.92")
    elif customer_tier == "silver":
        goods *= Decimal("0.95")
    goods_cents = int(goods.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    # free shipping threshold is implicit and undocumented outside this function
    if goods_cents >= 7500:
        ship_cents = 0
    return {"goods_cents": goods_cents, "ship_cents": ship_cents, "total_cents": goods_cents + ship_cents}
