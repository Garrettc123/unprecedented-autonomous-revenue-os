from __future__ import annotations

from data_room.ledger import EvidenceLedger

OPERATOR_EMAILS = {"carrolgarrett55@gmail.com"}


class PaymentProjection:
    """GAR-531. Paid is written only from a signature-verified Stripe event.

    Internal callers cannot manufacture paid. Test mode, card 4242, and
    operator self-pay are recorded and excluded from customer cash.
    """

    def __init__(self, ledger: EvidenceLedger, operator_emails: set[str] | None = None):
        self.ledger = ledger
        self.operator_emails = {e.lower() for e in (operator_emails or OPERATOR_EMAILS)}
        self.paid_ids: set[str] = set()

    def apply(self, event: dict, signature_verified: bool) -> dict:
        event_id = str(event.get("id", ""))
        obj = event.get("data", {}).get("object", {})
        livemode = bool(event.get("livemode"))
        paid_flag = obj.get("paid") is True or obj.get("payment_status") == "paid"
        last4 = (
            (obj.get("payment_method_details") or {})
            .get("card", {})
            .get("last4", obj.get("last4", ""))
        )
        email = str(obj.get("customer_email") or obj.get("receipt_email") or "").lower()
        if not signature_verified:
            kind = "rejected_unverified"
            cash = False
        elif not paid_flag:
            kind = "unpaid"
            cash = False
        elif not livemode:
            kind = "testmode"
            cash = False
        elif last4 == "4242":
            kind = "live_mode_test_card"
            cash = False
        elif email in self.operator_emails:
            kind = "operator_self_pay"
            cash = False
        else:
            kind = "customer_cash"
            cash = True
            self.paid_ids.add(event_id)
        row = self.ledger.append("payment.projection", {
            "event_id": event_id,
            "kind": kind,
            "cash": cash,
            "amount_usd": (obj.get("amount_received") or obj.get("amount_paid") or 0) / 100,
        })
        return {"kind": kind, "cash": cash, "evidence_hash": row["hash"], "onboarding": cash}
