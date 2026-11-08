#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 15 — enforceable evidence-gate (SINGULARIS Ф1).

Закон: эффект без evidence невозможен. Каждое действие субъекта дописывает
JSONL-строку в хеш-цепь; верификатор пересчитывает цепь только по артефактам.
Budget kill-switch — стена, не настройка: превышение дневного бюджета = отказ
в append (код 4), а не предупреждение. Scope вне политики актора = отказ
(код 3). Повреждение цепи ловит --verify (код 5).

Только stdlib, Python 3.11.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EMPTY_POLICY = {"scopes": {}, "budget_per_day": {}}


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_policy(path: Path) -> dict:
    if not path.exists():
        return dict(EMPTY_POLICY)
    return json.loads(path.read_text(encoding="utf-8"))


def chain_of(entries: list[dict]) -> str | None:
    return entries[-1]["entry_sha256"] if entries else None


def cmd_append(ledger: Path, policy_p: Path, actor: str, action: str, scope: str,
               proof: Path | None) -> int:
    policy = load_policy(policy_p)
    allowed = policy.get("scopes", {}).get(actor)
    if not allowed or not any(fnmatch.fnmatch(scope, pat) for pat in allowed):
        print(f"SCOPE_VIOLATION: актор «{actor}» не имеет права на зону «{scope}» — "
              "эффект без evidence невозможен (стена Ф1)")
        return 3
    entries = read_lines(ledger)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = sum(1 for e in entries if e.get("actor") == actor and str(e.get("ts", "")).startswith(today))
    limit = policy.get("budget_per_day", {}).get(actor)
    if limit is not None and used >= limit:
        print(f"BUDGET_EXCEED: актор «{actor}» исчерпал дневной бюджет ({used}/{limit}) — "
              "kill-switch это стена, не настройка")
        return 4
    prev = chain_of(entries)
    proof_sha = sha(proof.read_bytes()) if proof is not None and proof.exists() else None
    entry = {
        "seq": len(entries) + 1,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": actor,
        "action": action,
        "scope": scope,
        "proof_sha256": proof_sha,
        "prev": prev,
    }
    entry["entry_sha256"] = sha(canonical(entry))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"appended seq={entry['seq']} actor={actor} action={action} scope={scope}")
    return 0


def cmd_verify(ledger: Path) -> int:
    entries = read_lines(ledger)
    prev: str | None = None
    for i, e in enumerate(entries, 1):
        if e.get("seq") != i:
            print(f"CHAIN_BROKEN: дыра в нумерации seq на строке {i} "
                  f"(ожидалось {i}, найдено {e.get('seq')})")
            return 2
        body = {k: v for k, v in e.items() if k != "entry_sha256"}
        if sha(canonical(body)) != e.get("entry_sha256"):
            print(f"TAMPERED: хеш строки {i} не сходится")
            return 5
        if prev is not None and e.get("prev") != prev:
            print(f"TAMPERED: ссылка prev на строке {i} не совпадает с предыдущим хешем")
            return 5
        prev = e.get("entry_sha256")
    print(f"verifier: OK, строк в цепи: {len(entries)}")
    return 0


def cmd_selftest(tmp: Path) -> None:
    ledger = tmp / "ledger.jsonl"
    policy_p = tmp / "policy.json"
    policy_p.write_text(json.dumps({"scopes": {"bot": ["src/**"]},
                                    "budget_per_day": {"bot": 2}}, ensure_ascii=False),
                        encoding="utf-8")
    assert cmd_append(ledger, policy_p, "bot", "edit", "src/a.md", None) == 0
    assert cmd_append(ledger, policy_p, "bot", "edit", "docs/b.md", None) == 3   # scope violation
    assert cmd_append(ledger, policy_p, "bot", "edit", "src/b.md", None) == 0
    assert cmd_append(ledger, policy_p, "bot", "edit", "src/c.md", None) == 4   # budget exceed
    assert cmd_verify(ledger) == 0
    lines = ledger.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["scope"] = "secrets/**"
    lines[0] = json.dumps(first, ensure_ascii=False)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert cmd_verify(ledger) == 5                                              # tamper caught
    print("selftest: OK (append, scope violation → 3, budget exceed → 4, "
          "chain verify → 0, tamper → 5)")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Enforceable evidence-gate (issue 15, SINGULARIS Ф1)")
    ap.add_argument("--ledger", default="state/evidence-gate/ledger.jsonl")
    ap.add_argument("--policy", default="state/evidence-gate/policy.json")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--actor")
    ap.add_argument("--action")
    ap.add_argument("--scope")
    ap.add_argument("--proof", help="файл-доказательство: его sha256 входит в запись")
    args = ap.parse_args()
    if args.selftest:
        with tempfile.TemporaryDirectory() as td:
            cmd_selftest(Path(td))
        return 0
    if args.verify:
        return cmd_verify(Path(args.ledger))
    if args.append:
        if not (args.actor and args.action and args.scope):
            ap.error("--append требует --actor, --action, --scope")
        proof = Path(args.proof) if args.proof else None
        return cmd_append(Path(args.ledger), Path(args.policy),
                          args.actor, args.action, args.scope, proof)
    ap.error("укажите --append, --verify или --selftest")


if __name__ == "__main__":
    raise SystemExit(main())
