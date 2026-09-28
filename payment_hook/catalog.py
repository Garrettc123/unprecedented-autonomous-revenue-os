"""Live Stripe catalog for the public A wedge. No invented prices."""

from __future__ import annotations

from typing import Any

LIVE_PUBLIC_WEDGE: dict[str, dict[str, Any]] = {
    "MLS-497": {
        "sku": "MLS-497",
        "name": "Mark the leads that sat",
        "price_cents": 49700,
        "currency": "usd",
        "mode": "payment",
        "product_id": "prod_VF79GXA9nf3MQe",
        "price_id": "price_1UEcuyFKGbk21LK5mqhbKQWZ",
        "payment_link_id": "plink_1UEcv4FKGbk21LK57hRic0dR",
        "checkout": "https://buy.stripe.com/8x2eVddjf0hQ86Tf0f43S2h",
        "storefront": "https://garrettc123.github.io/",
        "fulfillment": "crm-export-review",
        "credits_toward": "LB-2500",
    },
    "LB-2500": {
        "sku": "LB-2500",
        "name": "Lead backup — callback clock",
        "price_cents": 250000,
        "currency": "usd",
        "mode": "payment",
        "product_id": "prod_VFSmjnUgB0MfM9",
        "price_id": "price_1UExqgFKGbk21LK5MWTXsSZr",
        "payment_link_id": "plink_1UGpMIFKGbk21LK5RHl8asRI",
        "checkout": "https://buy.stripe.com/14AdR95QN3u2af14lB43S2j",
        "storefront": "https://garrettc123.github.io/",
        "fulfillment": "crm-clock-install",
        "credits_toward": None,
    },
}

DEFAULT_SKU = "MLS-497"


def sku(code: str | None = None) -> dict[str, Any]:
    code = (code or DEFAULT_SKU).upper()
    if code not in LIVE_PUBLIC_WEDGE:
        raise KeyError(f"sku not on public wedge: {code}")
    return dict(LIVE_PUBLIC_WEDGE[code])
