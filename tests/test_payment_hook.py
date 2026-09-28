import unittest

from payment_hook.catalog import sku
from payment_hook.hook import apply_paid_event, attach_checkout


class PaymentHookTests(unittest.TestCase):
    def test_live_mls_price(self):
        offer = sku("MLS-497")
        self.assertEqual(offer["price_cents"], 49700)
        self.assertTrue(offer["checkout"].startswith("https://buy.stripe.com/"))

    def test_attach_requires_commit(self):
        blocked = attach_checkout("MLS-497", confidence=0.2)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["closed"], 0)

    def test_attach_does_not_fake_close(self):
        attached = attach_checkout("MLS-497", confidence=0.91)
        self.assertEqual(attached["status"], "attached")
        self.assertEqual(attached["cmc"], "commit")
        self.assertEqual(attached["closed"], 0)
        self.assertEqual(attached["sku"], "MLS-497")

    def test_paid_event_opens_fulfillment(self):
        paid = apply_paid_event(
            {
                "sku": "MLS-497",
                "amount_total": 49700,
                "customer_email": "broker@example.com",
                "checkout_session_id": "cs_test_unused",
            }
        )
        self.assertEqual(paid["status"], "paid")
        self.assertEqual(paid["closed"], 1)
        self.assertEqual(paid["fulfillment"]["sku"], "MLS-497")

    def test_wrong_amount_blocked(self):
        paid = apply_paid_event({"sku": "MLS-497", "amount_total": 1})
        self.assertEqual(paid["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
