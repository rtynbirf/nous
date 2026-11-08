#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 17 — страж write-lease: матрица §5 как код.

Протокол: перед мутацией агент дописывает в leases/LEASES.jsonl строку-аренду
{"lease_id","agent","repo","zone":{"paths":[...],"refs":[...]},"t_start",
"t_end","intent","sha_before"}; после — строку release {"type":"release",
"lease_id","status":"done|conflict"}. Заявил окно → сделал → release.
Просроченная аренда мертва сама (TTL) — уборка не нужна. sha_before —
fencing-доказательство (Клеппманн); null допустим только у записи-прародителя.

Страж проверяет: (1) мутация покрыта живой арендой; (2) пересечение зоны И
окна у двух разных агентов → код 1 с печатью обоих lease_id; (3) чужие зоны
(релизы, теги v*, ветки dependabot/*) → «409: перечитай §5, аренда недоступна».
При 409 ретрая нет: перечитать карту и взять окно позже.
Только stdlib, Python 3.11.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FORBIDDEN_REF_PATTERNS = ["refs/tags/v*", "refs/heads/dependabot/*", "refs/heads/release*"]


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def leases_of(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("lease_id") and not r.get("type")]


def released_ids(rows: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in rows:
        if r.get("type") == "release":
            out.setdefault(str(r.get("lease_id")), str(r.get("status", "")))
    return out


def is_live(lease: dict, closed: dict[str, str], now: datetime) -> bool:
    if closed.get(str(lease.get("lease_id"))) in ("done", "conflict"):
        return False
    return parse_ts(lease["t_start"]) <= now <= parse_ts(lease["t_end"])


def zone_of(lease: dict) -> dict:
    z = lease.get("zone", {})
    if isinstance(z, str):
        return {"paths": [z], "refs": []}
    return {"paths": list(z.get("paths", [])), "refs": list(z.get("refs", []))}


def zone_hits(zone: dict, paths: list[str], ref: str | None) -> bool:
    for p in paths:
        for pat in zone["paths"]:
            if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(pat, p):
                return True
    if ref:
        for pat in zone["refs"]:
            if fnmatch.fnmatch(ref, pat) or fnmatch.fnmatch(pat, ref):
                return True
    return False


def windows_overlap(a: dict, b: dict) -> bool:
    return (parse_ts(a["t_start"]) <= parse_ts(b["t_end"])
            and parse_ts(b["t_start"]) <= parse_ts(a["t_end"]))


def zone_allowed(ref: str | None) -> tuple[int, str]:
    if ref:
        for pat in FORBIDDEN_REF_PATTERNS:
            if fnmatch.fnmatch(ref, pat):
                return 1, (f"409: перечитай §5 — аренда недоступна на чужую зону "
                           f"(ref {ref} под «{pat}»)")
    return 0, "зона доступна"


def check_new(path: Path, candidate: dict, now: datetime) -> tuple[int, str]:
    required = ("lease_id", "agent", "repo", "zone", "t_start", "t_end", "intent")
    missing = [k for k in required if k not in candidate]
    if missing:
        return 2, f"кандидат аренды неполон: нет полей {', '.join(missing)}"
    if "sha_before" not in candidate:
        return 2, "кандидат без fencing-доказательства sha_before " \
                  "(null — только для записи-прародителя)"
    for ref_pat in zone_of(candidate)["refs"]:
        for pat in FORBIDDEN_REF_PATTERNS:
            if fnmatch.fnmatch(str(ref_pat), pat):
                return 1, (f"409: перечитай §5 — аренда недоступна на чужую зону "
                           f"(refs-шаблон «{ref_pat}»)")
    rows = load(path)
    closed = released_ids(rows)
    for other in leases_of(rows):
        if other.get("agent") == candidate.get("agent"):
            continue
        zo, zc = zone_of(other), zone_of(candidate)
        paths_hit = any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(pat, p)
                        for p in zc["paths"] for pat in zo["paths"])
        refs_hit = any(fnmatch.fnmatch(r, pat) or fnmatch.fnmatch(pat, r)
                       for r in zc["refs"] for pat in zo["refs"])
        if ((paths_hit or refs_hit) and windows_overlap(candidate, other)
                and is_live(other, closed, now)):
            return 1, (f"409: пересечение зоны и окна у {candidate.get('lease_id')} "
                       f"и {other.get('lease_id')} — перечитай §5")
    return 0, "аренда принимается: пересечений с живыми арендами других агентов нет"


def event_check(path: Path, event: str, repo: str, paths: list[str], ref: str | None,
                now: datetime, enforce: bool) -> tuple[int, str]:
    rc, msg = zone_allowed(ref)
    if rc:
        return (rc, msg) if enforce else (0, f"[report] {msg}")
    rows = load(path)
    closed = released_ids(rows)
    covering = [l for l in leases_of(rows)
                if str(l.get("repo")) == repo and is_live(l, closed, now)
                and zone_hits(zone_of(l), paths, ref)]
    if covering:
        return 0, f"мутация покрыта живой арендой: {', '.join(str(l['lease_id']) for l in covering)}"
    text = (f"409: перечитай — мутация ({event}, {repo}, paths={paths or '-'}, "
            f"ref={ref or '-'}) без живой аренды")
    return (1, text) if enforce else (0, f"[report] {text}")


def selftest() -> int:
    now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "LEASES.jsonl"
        base = {"repo": "rtynbirf/nous", "zone": {"paths": ["blood/**"], "refs": []},
                "t_start": "2026-11-09T00:00:00Z", "t_end": "2026-11-09T20:00:00Z",
                "sha_before": None}
        a = dict(base, lease_id="L-A", agent="agent-A", intent="тестовая аренда A")
        b = dict(base, lease_id="L-B", agent="agent-B",
                 t_start="2026-11-09T10:00:00Z", t_end="2026-11-09T18:00:00Z",
                 intent="тестовая аренда B, окно пересекается с A")
        path.write_text(json.dumps(a, ensure_ascii=False) + "\n"
                        + json.dumps(b, ensure_ascii=False) + "\n", encoding="utf-8")
        rc, msg = check_new(path, dict(b, lease_id="L-C", agent="agent-C"), now)
        # оба lease_id конфликтующей пары должны быть напечатаны
        assert rc == 1 and "L-C" in msg and ("L-A" in msg or "L-B" in msg), msg
        rc, msg = zone_allowed("refs/tags/v1.0.0")
        assert rc == 1 and msg.startswith("409"), msg
        rc, msg = event_check(path, "push", "rtynbirf/nous", ["blood/x.md"], None, now, True)
        assert rc == 0 and "L-A" in msg, msg
        rc, msg = event_check(path, "push", "rtynbirf/nous", ["quiet/x.md"], None, now, True)
        assert rc == 1 and msg.startswith("409"), msg
    print("selftest: OK (пересечение аренд → 1 с двумя id; чужой ref → 409; "
          "своя в окне → 0; мутация без аренды → 409)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Страж write-lease (issue 17)")
    ap.add_argument("--leases", default="leases/LEASES.jsonl")
    ap.add_argument("--event", choices=["push", "pull_request"])
    ap.add_argument("--repo")
    ap.add_argument("--paths", nargs="*", default=[])
    ap.add_argument("--ref")
    ap.add_argument("--mode", choices=["report", "enforce"], default="report")
    ap.add_argument("--check-new", help="проверить JSON-файл кандидата-аренды перед записью")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    now = datetime.now(timezone.utc)
    if args.check_new:
        candidate = json.loads(Path(args.check_new).read_text(encoding="utf-8"))
        rc, msg = check_new(Path(args.leases), candidate, now)
        print(msg)
        return rc
    if args.event and args.repo:
        rc, msg = event_check(Path(args.leases), args.event, args.repo, args.paths,
                              args.ref, now, args.mode == "enforce")
        print(msg)
        return rc
    ap.error("укажите --selftest, --check-new FILE или --event E --repo R")


if __name__ == "__main__":
    raise SystemExit(main())
