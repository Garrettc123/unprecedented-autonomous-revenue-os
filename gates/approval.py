from __future__ import annotations

from data_room.ledger import EvidenceLedger


class ApprovalGate:
    """GAR-530. Outbound dial or send is refused without a policy_decision_id.

    The id must already exist in the approval set. This module does not issue
    approvals and does not place calls.
    """

    def __init__(self, ledger: EvidenceLedger, approvals: set[str] | None = None):
        self.ledger = ledger
        self.approvals = set(approvals or set())

    def grant(self, policy_decision_id: str, actor: str) -> dict:
        self.approvals.add(policy_decision_id)
        return self.ledger.append("approval.granted", {
            "policy_decision_id": policy_decision_id,
            "actor": actor,
        })

    def authorize(self, channel: str, target: str, policy_decision_id: str | None) -> dict:
        if channel not in {"dial", "sms", "email", "dm"}:
            decision = "refused"
            reason = "unknown channel"
        elif not policy_decision_id or policy_decision_id not in self.approvals:
            decision = "refused"
            reason = "missing or unknown policy_decision_id"
        else:
            decision = "allowed"
            reason = "approval id matched"
        row = self.ledger.append("outreach.decision", {
            "channel": channel,
            "target": target,
            "policy_decision_id": policy_decision_id or "",
            "decision": decision,
            "reason": reason,
        })
        return {"decision": decision, "reason": reason, "evidence_hash": row["hash"]}
