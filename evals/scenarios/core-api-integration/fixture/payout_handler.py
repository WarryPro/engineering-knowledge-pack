"""HTTP handler currently calls ClearSettle inline."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def confirm_payout(request, db, settings):
    payout_id = request["payout_id"]
    row = db.get_payout(payout_id)
    if row is None or row["status"] != "approved":
        return {"ok": False, "error": "not_approved"}

    body = json.dumps(
        {
            "merchant_ref": payout_id,
            "amount_cents": row["amount_cents"],
            "currency": row["currency"],
            "destination": row["destination"],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        settings["clearsettle_url"] + "/v2/payouts",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer demo-token",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # transient and permanent failures currently look the same to callers
        return {"ok": False, "error": f"provider_http_{exc.code}"}
    except Exception:
        return {"ok": False, "error": "provider_unreachable"}

    db.mark_sent(payout_id, payload.get("provider_id"))
    return {"ok": True, "provider_id": payload.get("provider_id")}
