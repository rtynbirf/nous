"""src/runtime/harness · receipts: append-only, hash-chained журнал receipts (ADR-0011).

Доверенная сторона (harness) пишет сюда; модель может только ССЫЛАТЬСЯ на rid.
Правка любой записи ломает цепь prev-хешей; правка последней записи ломает
внешний якорь head-хеша (файл .head — вне досягаемости модели; в проде — HMAC).

Канонический хеш совместим с src/lib/ledger.sh (проверяемость одним
верификатором): json.dumps(sort_keys=True, ensure_ascii=False,
separators=(",", ":")) -> sha256. Genesis-хеш = "0"*64 — как в ledger.sh.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

GENESIS = "0" * 64

# receipt.kind -> type из schemas/evidence-entry.schema.json (enum)
_EVIDENCE_TYPE = {
    "ACTION": "intermediate",
    "PROPOSAL": "proposal",
    "REPORT": "final",
    "VERIFIER": "verifier_decision",
    "ABORT": "abort",
}


def canonical(obj) -> str:
    """Канонический JSON: тот же канон, что в src/lib/ledger.sh (ADR-0011)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iso_ts(epoch) -> str:
    """epoch -> ISO-8601 UTC (формат timestamp схемы evidence-entry)."""
    if isinstance(epoch, (int, float)):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))
    return str(epoch)


class ReceiptLog:
    """Append-only журнал: каждая запись ссылается на хеш предыдущей.

    Только harness вызывает mint(); модель получает rid и обязана ссылаться
    на него. Голое утверждение о мире без rid детектируется Auditor'ом.
    """

    def __init__(self, path: str, head_path: str = None):
        self.path = path
        self.head_path = head_path or path + ".head"
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.records = []
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.records.append(json.loads(line))

    def head(self) -> str:
        return sha(canonical(self.records[-1]).encode("utf-8")) if self.records else GENESIS

    def verify_chain(self):
        """(ok, detail): prev-цепь + сверка с внешним якорем .head (если есть)."""
        prev = GENESIS
        for i, r in enumerate(self.records):
            if r.get("prev") != prev:
                return False, (f"record {i} ({r.get('rid')}): prev-hash mismatch "
                               f"(history tampered)")
            prev = sha(canonical(r).encode("utf-8"))
        if os.path.exists(self.head_path):
            with open(self.head_path, "r", encoding="utf-8") as f:
                anchored = f.read().strip()
            if anchored != self.head():
                return False, (f"head anchor mismatch: anchored={anchored[:12]}.. "
                               f"actual={self.head()[:12]}.. (last record tampered)")
        return True, "ok"

    def mint(self, **fields) -> dict:
        """Записать receipt одним append; обновить внешний якорь head-хеша."""
        rec = {"rid": f"R{len(self.records) + 1:04d}",
               "ts": round(time.time(), 3),
               "prev": self.head(), **fields}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(canonical(rec) + "\n")
        self.records.append(rec)
        with open(self.head_path, "w", encoding="utf-8") as f:
            f.write(self.head())
        return rec


def to_evidence_entry(rec: dict, run_id: str, subject_id: str,
                      claim: str = None, verifier_decision: str = None) -> dict:
    """Маппинг receipt -> запись schemas/evidence-entry.schema.json.

    Обязательные поля схемы: evidence_id, run_id, subject_id, timestamp,
    type, claim, hash. prev_hash/hash — та же цепь: hash записи = sha256
    канонического JSON записи (как считает verify_chain и ledger.sh).
    Дополнительные поля схемы разрешены (additionalProperties: true).
    """
    fallback = f"{rec.get('tool', '?')}.{rec.get('op', '?')} -> {rec.get('status', '?')}"
    text = claim or rec.get("reason") or rec.get("error") or fallback
    if len(text) < 5:  # schema: claim minLength 5
        text = fallback
    entry = {
        "evidence_id": rec.get("rid"),
        "run_id": run_id,
        "subject_id": subject_id,
        "timestamp": iso_ts(rec.get("ts")),
        "type": _EVIDENCE_TYPE.get(rec.get("kind", "ACTION"), "intermediate"),
        "claim": text,
        "prev_hash": rec.get("prev", GENESIS),
        "hash": sha(canonical(rec).encode("utf-8")),
    }
    if rec.get("tool"):
        action = {"op": f"{rec['tool']}.{rec.get('op', '?')}"}
        if rec.get("path"):
            action["path"] = rec["path"]
        if rec.get("output_hash"):
            action["hash"] = rec["output_hash"]
        entry["actions"] = [action]
    if verifier_decision is not None:
        entry["verifier_decision"] = verifier_decision
    return entry
