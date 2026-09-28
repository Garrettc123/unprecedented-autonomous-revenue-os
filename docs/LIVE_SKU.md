# Live public wedge (reconciled 2026-09-27)

Source of truth: Stripe livemode `acct_1SS3dpFKGbk21LK5` + storefront https://garrettc123.github.io/

Do not sell the retired $47 HVAC audit as the public A offer this hour.

| SKU | Offer | Cents | Checkout |
|---|---|---:|---|
| MLS-497 | Mark the leads that sat | 49700 | https://buy.stripe.com/8x2eVddjf0hQ86Tf0f43S2h |
| LB-2500 | Lead backup — callback clock | 250000 | https://buy.stripe.com/14AdR95QN3u2af14lB43S2j |

MLS-497 credits toward LB-2500 if they continue.

Payment hook: `payment_hook.attach_checkout` may publish the link only after CMC `commit`. `apply_paid_event` is the only path that sets `closed=1`.
