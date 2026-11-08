#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 16 — «Evidence-пломба» вердикта (усилена до hash-chain).

После зелёного прогона: sha256 файла вердикта → append-строка evidence.log:
  {"seq", "ts", "run_id", "verdict_sha256", "prev_sha256", "artifact_url"}
Рядом кладётся сайдкар `<verdict>.seal.json` с evidence_sha256 и run_id.
Файл вердикта не переписывается (append-only дух): пломба живёт в леджере и
сайдкаре, а sha256sum файла всегда можно сверить со строкой леджера.
Усиление Волны 3 (по «Ходу для роя» issue 16): в каждой записи есть
prev_sha256 — hash-chain с первой записи; повторная пломба того же run_id не
создаёт дубль. Только stdlib, Python 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_seal(ledger: Path, verdict: Path, run_id: str, artifact_url: str) -> int:
    if not verdict.exists():
        print(f"вердикт не найден ({verdict}) — пломба пропущена; "
              "запустите после зелёного прогона")
        return 0
    entries = read_log(ledger)
    for e in entries:
        if e.get("run_id") == run_id:
            print(f"run_id {run_id} уже запечатан (seq {e.get('seq')}) — "
                  "append-only, дубль не создаётся")
            return 0
    digest = sha_file(verdict)
    record = {
        "seq": len(entries) + 1,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "verdict_sha256": digest,
        "prev_sha256": entries[-1].get("verdict_sha256") if entries else None,
        "artifact_url": artifact_url,
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    sidecar = Path(str(verdict) + ".seal.json")
    sidecar.write_text(json.dumps({"evidence_sha256": digest, "run_id": run_id,
                                   "sealed_at": record["ts"], "seq": record["seq"]},
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"запечатано: seq={record['seq']} run_id={run_id} verdict_sha256={digest}")
    return 0


def cmd_selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        verdict = root / "verdict.json"
        verdict.write_text('{"ok": true, "points": 15}\n', encoding="utf-8")
        ledger = root / "evidence.log"
        assert cmd_seal(ledger, verdict, "run-2026-11-09", "") == 0
        assert cmd_seal(ledger, verdict, "run-2026-11-09", "") == 0  # дубль не пишется
        entries = read_log(ledger)
        assert len(entries) == 1 and entries[0]["prev_sha256"] is None
        side = Path(str(verdict) + ".seal.json")
        data = json.loads(side.read_text(encoding="utf-8"))
        assert data["evidence_sha256"] == sha_file(verdict)
        assert data["run_id"] == "run-2026-11-09"
    print("selftest: OK (пломба, сайдкар с evidence_sha256, защита от дубля run_id)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Evidence-пломба вердикта (issue 16)")
    ap.add_argument("--ledger", default="state/evidence/evidence.log")
    ap.add_argument("--seal", action="store_true")
    ap.add_argument("--verdict", help="JSON-файл вердикта")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--artifact-url", default="")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return cmd_selftest()
    if args.seal:
        if not args.verdict:
            ap.error("--seal требует --verdict")
        return cmd_seal(Path(args.ledger), Path(args.verdict),
                        args.run_id, args.artifact_url)
    ap.error("укажите --seal или --selftest")


if __name__ == "__main__":
    raise SystemExit(main())
