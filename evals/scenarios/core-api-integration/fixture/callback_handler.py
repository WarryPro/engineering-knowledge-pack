"""ClearSettle callback endpoint."""

from __future__ import annotations


def clearsettle_callback(request, db):
    provider_id = request.get("provider_id")
    merchant_ref = request.get("merchant_ref")
    status = request.get("status")
    # duplicate deliveries are possible; current code rewrites status each time
    db.set_provider_status(merchant_ref, provider_id, status)
    return {"received": True}
