import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from data_room.ledger import EvidenceLedger
from gates.approval import ApprovalGate
from payment_hook.projection import PaymentProjection


class DataRoomTests(unittest.TestCase):
    def test_chain_detects_tamper(self):
        with TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(str(Path(tmp) / "e.jsonl"))
            ledger.append("boot", {"component": "data_room"})
            ledger.append("note", {"text": "evidence"})
            self.assertTrue(ledger.verify()["ok"])
            self.assertFalse(ledger.verify()["immutable"])
            ledger.rows[0]["payload"]["component"] = "forged"
            self.assertFalse(ledger.verify()["ok"])

    def test_send_refused_without_approval(self):
        with TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(str(Path(tmp) / "e.jsonl"))
            gate = ApprovalGate(ledger)
            refused = gate.authorize("dm", "jordan", None)
            self.assertEqual(refused["decision"], "refused")
            gate.grant("pd_1", "garrett")
            allowed = gate.authorize("dm", "jordan", "pd_1")
            self.assertEqual(allowed["decision"], "allowed")

    def test_unverified_webhook_is_not_cash(self):
        with TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(str(Path(tmp) / "e.jsonl"))
            projection = PaymentProjection(ledger)
            event = {"id": "evt_1", "livemode": True, "data": {"object": {"paid": True, "amount_paid": 4700, "customer_email": "shop@example.com", "last4": "1881"}}}
            bad = projection.apply(event, signature_verified=False)
            good = projection.apply(event, signature_verified=True)
            card = projection.apply({**event, "id": "evt_2", "data": {"object": {**event["data"]["object"], "last4": "4242"}}}, True)
            self.assertFalse(bad["cash"])
            self.assertTrue(good["cash"])
            self.assertFalse(card["cash"])


if __name__ == "__main__":
    unittest.main()
