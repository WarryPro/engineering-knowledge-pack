"""Representative brittle tests (excerpt)."""

from checkout import Checkout


class FakeInventory:
    def __init__(self):
        self.calls = []

    def reserve(self, sku, qty):
        self.calls.append((sku, qty))
        return {"hold_id": "H1", "reserved_qty": qty}


class FakePayments:
    def charge(self, amount, method):
        return {"accepted": True, "tx_id": "T1"}


class FakeOrders:
    def create(self, cart, hold_id, tx_id):
        return "O1"


def test_place_calls_inventory_then_payments_then_orders():
    inventory, payments, orders = FakeInventory(), FakePayments(), FakeOrders()
    result = Checkout(inventory, payments, orders).place(
        {"sku": "A", "qty": 1, "total_cents": 100, "payment_method": "card"}
    )
    assert result["ok"] is True
    assert inventory.calls == [("A", 1)]


def test_place_returns_order_id_from_orders_collaborator():
    result = Checkout(FakeInventory(), FakePayments(), FakeOrders()).place(
        {"sku": "A", "qty": 1, "total_cents": 100, "payment_method": "card"}
    )
    assert result == {"ok": True, "order_id": "O1"}
