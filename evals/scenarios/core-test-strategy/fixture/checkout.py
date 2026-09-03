"""Simplified checkout orchestration."""

from __future__ import annotations


class Checkout:
    def __init__(self, inventory, payments, orders):
        self.inventory = inventory
        self.payments = payments
        self.orders = orders

    def place(self, cart):
        reservation = self.inventory.reserve(cart["sku"], cart["qty"])
        # partial reservation currently treated as success if any hold id exists
        if reservation.get("hold_id"):
            charge = self.payments.charge(cart["total_cents"], cart["payment_method"])
            if not charge.get("accepted"):
                return {"ok": False, "reason": "payment_declined"}
            order_id = self.orders.create(cart, reservation["hold_id"], charge["tx_id"])
            return {"ok": True, "order_id": order_id}
        return {"ok": False, "reason": "unavailable"}
