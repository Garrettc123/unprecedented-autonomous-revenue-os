"""Attach checkout only after CMC commit. Paid events open fulfillment. No fake closes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from payment_hook.catalog import sku as resolve_sku
from payment_hook.fulfillment import fulfillment_packet

COMMIT_CONFIDENCE = 0.72


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def attach_checkout(
    sku_code: str = "MLS-497",
    *,
    confidence: float = 0.91,
    contradictions: int = 0,
    paid: bool = False,
) -> dict[str, Any]:
    offer = resolve_sku(sku_code)
    if contradictions >= 2:
        decision = "abort"
    elif confidence < COMMIT_CONFIDENCE:
        decision = "escalate"
    else:
        decision = "commit"

    if decision != "commit":
        return {
            "status": "blocked",
            "state": "blocked",
            "cmc": decision,
            "closed": 0,
            "sku": offer["sku"],
            "reason": "CMC refused checkout attach",
            "attached_at": _now(),
        }

    return {
        "status": "attached",
        "state": "monetizing" if not paid else "fulfilling",
        "cmc": "commit",
        "closed": 0 if not paid else 1,
        "sku": offer["sku"],
        "price_cents": offer["price_cents"],
        "checkout": offer["checkout"],
        "price_id": offer["price_id"],
        "payment_link_id": offer["payment_link_id"],
        "product_id": offer["product_id"],
        "storefront": offer["storefront"],
        "attached_at": _now(),
        "note": "No close is recorded until a Stripe paid event hits apply_paid_event.",
    }


def apply_paid_event(event: dict[str, Any]) -> dict[str, Any]:
    """Idempotent paid-event handler. Does not charge anyone."""
    sku_code = str(event.get("sku") or "MLS-497")
    offer = resolve_sku(sku_code)
    session_id = str(event.get("checkout_session_id") or event.get("id") or "")
    email = str(event.get("customer_email") or "")
    amount = int(event.get("amount_total") or offer["price_cents"])
    if amount != int(offer["price_cents"]):
        return {
            "status": "blocked",
            "reason": "paid amount does not match live SKU",
            "expected_cents": offer["price_cents"],
            "got_cents": amount,
        }
    packet = fulfillment_packet(offer["sku"], buyer_email=email, session_id=session_id)
    return {
        "status": "paid",
        "state": "fulfilling",
        "cmc": "commit",
        "closed": 1,
        "sku": offer["sku"],
        "amount_cents": amount,
        "checkout_session_id": session_id,
        "fulfillment": packet,
        "paid_at": _now(),
    }
