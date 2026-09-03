"""Current fulfillment entry used by checkout HTTP and a warehouse script."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class FulfillResult:
    ok: bool
    tracking: str | None
    message: str


class FulfillmentService:
    def __init__(self, db: Any, notifier: Any) -> None:
        self.db = db
        self.notifier = notifier

    def fulfill(self, payload: dict) -> FulfillResult:
        # request-shaped validation mixed with business checks
        if "order_id" not in payload or "sku" not in payload:
            return FulfillResult(False, None, "invalid payload")
        if int(payload.get("qty", 0)) <= 0:
            return FulfillResult(False, None, "qty must be positive")

        order = self.db.fetch_order(payload["order_id"])
        if order is None:
            return FulfillResult(False, None, "unknown order")
        if order["status"] != "paid":
            return FulfillResult(False, None, "order not payable for fulfillment")

        # business decision currently inlined with infrastructure
        if order["region"] == "EU" and payload["sku"].startswith("HAZ-"):
            return FulfillResult(False, None, "restricted sku for region")

        stock = self.db.lock_stock(payload["sku"], int(payload["qty"]))
        if not stock:
            return FulfillResult(False, None, "insufficient stock")

        body = json.dumps(
            {
                "ref": order["order_id"],
                "sku": payload["sku"],
                "qty": payload["qty"],
                "ship_to": order["address"],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.parcelgo.example/v1/shipments",
            data=body,
            headers={"Content-Type": "application/json", "X-Api-Key": "demo"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            carrier = json.loads(resp.read().decode("utf-8"))

        self.db.mark_fulfilled(order["order_id"], carrier["tracking"])
        self.notifier.email(order["email"], f"Shipped {carrier['tracking']}")
        return FulfillResult(True, carrier["tracking"], "shipped")
