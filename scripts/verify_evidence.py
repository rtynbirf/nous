#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 16 — верификатор evidence-пломб (hash-chain).

Пересчитывает sha256 файла вердикта, проверяет монотонность seq, звенья
prev_sha256 и совпадение run_id с леджерной строкой. Любая ретушь истории
ловится: изменение байта вердикта → код 1; дыра в seq или разрыв цепи → код 2;
несовпадение/отсутствие run_id → код 3. --selftest доказывает поимку подделки
на тестах. Только stdlib, Python 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def verify(ledger: Path, verdict: Path | None, run_id: str | None) -> int:
    entries = read_log(ledger)
    prev: str | None = None
    for i, e in enumerate(entries, 1):
        if e.get("seq") != i:
            print(f"EVIDENCE_RED: дыра в нумерации seq на строке {i} "
                  f"(ожидалось {i}, найдено {e.get('seq')})")
            return 2
        if prev is not None and e.get("prev_sha256") != prev:
            print(f"EVIDENCE_RED: звено prev_sha256 разорвано на строке {i}")
            return 2
        prev = e.get("verdict_sha256")
    if run_id:
        if not any(e.get("run_id") == run_id for e in entries):
            print(f"EVIDENCE_RED: run_id {run_id} в леджере не найден")
            return 3
    if verdict is not None:
        if not verdict.exists():
            print(f"EVIDENCE_RED: файл вердикта не найден: {verdict}")
            return 3
        digest = sha_file(verdict)
        rows = [e for e in entries if e.get("verdict_sha256") == digest]
        if not rows:
            print("EVIDENCE_RED: sha256 вердикта отсутствует в леджере — "
                  "возможна ретушь истории")
            return 1
        if run_id and rows[0].get("run_id") != run_id:
            print("EVIDENCE_RED: run_id леджерной строки не совпадает с проверяемым")
            return 3
    print(f"evidence: OK (строк в цепи: {len(entries)})")
    return 0


def _seal_simple(ledger: Path, verdict: Path, run_id: str) -> None:
    """Мини-пломба только для selftest (полная — в seal_evidence.py)."""
    entries = read_log(ledger)
    record = {
        "seq": len(entries) + 1,
        "ts": "2026-11-09T00:00:00Z",
        "run_id": run_id,
        "verdict_sha256": sha_file(verdict),
        "prev_sha256": entries[-1]["verdict_sha256"] if entries else None,
        "artifact_url": "",
    }
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ledger = root / "evidence.log"
        v1 = root / "verdict1.json"
        v1.write_text('{"ok": true, "points": 15}\n', encoding="utf-8")
        _seal_simple(ledger, v1, "run-1")
        v2 = root / "verdict2.json"
        v2.write_text('{"ok": true, "points": 15, "n": 2}\n', encoding="utf-8")
        _seal_simple(ledger, v2, "run-2")
        assert verify(ledger, v1, "run-1") == 0
        # подделка одного байта вердикта → красная проверка (код 1)
        v1.write_text('{"ok": true, "points": 16}\n', encoding="utf-8")
        assert verify(ledger, v1, "run-1") == 1
        v1.write_text('{"ok": true, "points": 15}\n', encoding="utf-8")
        # удаление строки леджера → дыра в seq (код 2)
        lines = ledger.read_text(encoding="utf-8").splitlines()
        del lines[0]
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert verify(ledger, None, None) == 2
    print("selftest: OK (чистая цепь → 0; тампер байта → 1; удаление строки → 2)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Верификатор evidence-пломб (issue 16)")
    ap.add_argument("--ledger", default="state/evidence/evidence.log")
    ap.add_argument("--verdict", help="файл вердикта для сверки sha256")
    ap.add_argument("--run-id", help="ожидаемый run_id")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    return verify(Path(args.ledger),
                  Path(args.verdict) if args.verdict else None,
                  args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
