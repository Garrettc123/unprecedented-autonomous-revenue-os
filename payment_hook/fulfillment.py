"""Same-day fulfillment packet for paid public-wedge SKUs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def fulfillment_packet(sku_code: str, *, buyer_email: str = "", session_id: str = "") -> dict[str, Any]:
    stamped = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if sku_code == "LB-2500":
        return {
            "sku": sku_code,
            "window": "three business days after CRM details, rules, and payment",
            "collect": [
                "CRM name (Follow Up Boss or current system)",
                "lead source to cover",
                "owner of first call",
                "backup person",
                "team-defined stale-day rule",
            ],
            "deliver": [
                "timer on the covered source",
                "backup-person rule",
                "team-lead view of not-called and no-next-step",
            ],
            "buyer_email": buyer_email,
            "session_id": session_id,
            "reply_to": "gwc2780@gmail.com",
            "stamped_at": stamped,
        }
    return {
        "sku": sku_code,
        "window": "same day after CRM export lands",
        "collect": [
            "one CRM export",
            "one source",
            "up to 500 names",
            "last 30 days",
        ],
        "deliver": [
            "marked spreadsheet",
            "one-page count",
            "written rules for the current system",
        ],
        "credit": "MLS-497 comes off LB-2500 if they continue",
        "buyer_email": buyer_email,
        "session_id": session_id,
        "reply_to": "gwc2780@gmail.com",
        "stamped_at": stamped,
    }
