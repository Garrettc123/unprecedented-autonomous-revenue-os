from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


class EvidenceLedger:
    """Hash-chained evidence log.

    Each row binds to the previous hash. A rewritten earlier row breaks verify().
    This is tamper-evident. It is not immutable until a checkpoint hash is
    anchored outside this file, for example as a signed git tag. That anchor
    is not performed here.
    """

    GENESIS = "0" * 64

    def __init__(self, path: str = "data_room/evidence.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rows = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def append(self, kind: str, payload: dict) -> dict:
        prev = self.rows[-1]["hash"] if self.rows else self.GENESIS
        body = {"kind": kind, "payload": payload, "prev": prev, "seq": len(self.rows) + 1}
        digest = hashlib.sha256(canonical(body).encode()).hexdigest()
        row = {
            "seq": body["seq"],
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "prev": prev,
            "hash": digest,
            "payload": payload,
            "anchored": False,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        self.rows.append(row)
        return row

    def verify(self) -> dict:
        prev = self.GENESIS
        for index, row in enumerate(self.rows):
            body = {"kind": row["kind"], "payload": row["payload"], "prev": row["prev"], "seq": row["seq"]}
            expect = hashlib.sha256(canonical(body).encode()).hexdigest()
            if row["prev"] != prev or row["hash"] != expect or row["seq"] != index + 1:
                return {"ok": False, "broken_at": row.get("seq"), "immutable": False}
            prev = row["hash"]
        return {
            "ok": True,
            "rows": len(self.rows),
            "head": prev if self.rows else self.GENESIS,
            "immutable": False,
            "reason": "no external anchor",
        }

    def checkpoint(self) -> dict:
        status = self.verify()
        return {
            "head": status["head"],
            "rows": status["rows"],
            "anchor": "unsigned",
            "instruction": "Sign this head as a git tag before calling the room immutable.",
        }
