#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 13 — weekly-свип «Календаря организма».

7 пунктов одним проходом, отчёт одной строкой (в лог джобы и append-строкой в
state/sweep/log.jsonl). Закон заморозки: краснота > 72 ч → скрипт пишет
state/freeze/active.json (мутации автоматики заморожены до лечения); краснота
уходит → запись снимается тем же законом. Только stdlib, Python 3.11.

Источники (нет файла — норма первого прогона, пункт = «нет данных»):
  sweep-состояние: state/sweep/{tokens,secrets,open_prs,swarm}.json; вердикт-лог:
  state/green-guard/verdicts.jsonl; retention-days — текстово из
  .github/workflows/*.yml; sha256-строки — manifests/pins.yaml.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TOKEN_AGE_DAYS = 90   # ориентир GitHub: стандартный срок жизни токена/секрета
DPR_TAIL_DAYS = 7
RED_HOURS_FLAG = 24.0
FREEZE_HOURS = 72.0

def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

def read_jsonl(path: Path):
    if not path.exists():
        return None
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return None
    return rows

def age_days(iso: str, now: datetime) -> float:
    return (now - datetime.fromisoformat(str(iso).replace("Z", "+00:00"))).total_seconds() / 86400.0

def check_aging(label: str, path: Path, now: datetime) -> tuple[str, bool]:
    items = read_json(path)
    if items is None:
        return f"{label}: нет данных", False
    old = [str(i.get("name", "?")) for i in items
           if age_days(i["rotated_at"], now) > TOKEN_AGE_DAYS]
    detail = f"{label}: всего {len(items)}, старше {TOKEN_AGE_DAYS} д: {len(old)}"
    return (detail + (f" ({', '.join(old)})" if old else "")), bool(old)

def check_redness(state: Path, now: datetime) -> tuple[str, bool, float]:
    rows = read_jsonl(state / "green-guard" / "verdicts.jsonl")
    if rows is None:
        return "краснота-часы: нет данных", False, 0.0
    streak: dict[str, str] = {}
    for r in sorted(rows, key=lambda x: x["ts"]):
        cp = str(r.get("checkpoint", "?"))
        if str(r.get("status", "")).lower() == "red":
            streak.setdefault(cp, str(r["ts"]))
        else:
            streak.pop(cp, None)
    hours = max(((now - datetime.fromisoformat(t.replace("Z", "+00:00"))).total_seconds() / 3600.0
                 for t in streak.values()), default=0.0)
    return f"краснота-часы: макс {hours:.1f} ч", hours > RED_HOURS_FLAG, hours

def check_dpr_tail(state: Path, now: datetime) -> tuple[str, bool]:
    items = read_json(state / "sweep" / "open_prs.json")
    if items is None:
        return "ДПР-хвост: нет данных", False
    tail = [i for i in items if age_days(i["opened_at"], now) > DPR_TAIL_DAYS]
    return f"ДПР-хвост: открытых {len(items)}, старше {DPR_TAIL_DAYS} д: {len(tail)}", bool(tail)

def check_retention(repo_root: Path) -> tuple[str, bool]:
    wf_dir = repo_root / ".github" / "workflows"
    if not wf_dir.exists():
        return "retention-сходство: нет данных", False
    values: set[str] = set()
    for wf in wf_dir.glob("*.yml"):
        values.update(ln.split(":", 1)[1].strip()
                      for ln in wf.read_text(encoding="utf-8", errors="replace").splitlines()
                      if ln.strip().startswith("retention-days:"))
    if not values:
        return "retention-сходство: retention-days не найдены", False
    return (f"retention-сходство: значения {sorted(values)}", len(values) != 1)

def check_genome_pins(repo_root: Path) -> tuple[str, bool]:
    pins = repo_root / "manifests" / "pins.yaml"
    if not pins.exists():
        return "геном-пины: manifests/pins.yaml не найден", False
    n = sum(1 for ln in pins.read_text(encoding="utf-8", errors="replace").splitlines()
            if "sha256" in ln)
    return f"геном-пины: sha256-строк в pins.yaml: {n}", n == 0

def check_swarm(state: Path) -> tuple[str, bool]:
    items = read_json(state / "sweep" / "swarm.json")
    if items is None:
        return "рой-VERIFIED: нет данных", False
    bad = [str(i.get("agent", "?")) for i in items if i.get("status") != "VERIFIED"]
    return f"рой-VERIFIED: всего {len(items)}, не VERIFIED: {len(bad)}", bool(bad)

def run_sweep(repo_root: Path, now: datetime) -> tuple[str, list[str], bool, float]:
    state = repo_root / "state"
    parts: list[str] = []
    flags: list[str] = []
    checks: list[tuple[str, str, bool]] = []
    red_detail, red_flag, hours = check_redness(state, now)
    checks.append(("токены-возраст", *check_aging("токены", state / "sweep" / "tokens.json", now)))
    checks.append(("секреты-возраст", *check_aging("секреты", state / "sweep" / "secrets.json", now)))
    checks.append(("краснота-часы", red_detail, red_flag))
    checks.append(("ДПР-хвост", *check_dpr_tail(state, now)))
    checks.append(("retention-сходство", *check_retention(repo_root)))
    checks.append(("геном-пины", *check_genome_pins(repo_root)))
    checks.append(("рой-VERIFIED", *check_swarm(state)))
    for label, detail, flag in checks:
        parts.append(detail)
        if flag:
            flags.append(label)
    hours = check_redness(state, now)[2]
    freeze = hours > FREEZE_HOURS
    line = (f"SWEEP {now:%Y-%m-%d %H:%M}Z | " + " | ".join(parts)
            + f" | флаги: {', '.join(flags) if flags else 'нет'}"
            + f" | заморозка: {'АКТИВНА' if freeze else 'нет'}")
    return line, flags, freeze, hours

def persist(repo_root: Path, line: str, freeze: bool, hours: float, now: datetime) -> None:
    log = repo_root / "state" / "sweep" / "log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "line": line, "freeze": freeze}, ensure_ascii=False) + "\n")
    active = repo_root / "state" / "freeze" / "active.json"
    if freeze and not active.exists():
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_text(json.dumps({
            "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reason": f"краснота {hours:.1f} ч > {FREEZE_HOURS:.0f} ч — закон календаря организма (issue 13)",
            "red_hours": round(hours, 2)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif not freeze and active.exists():
        active.unlink()  # краснота ушла — заморозка снята тем же законом

def selftest() -> int:
    now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "state" / "sweep").mkdir(parents=True)
        (root / "state" / "sweep" / "tokens.json").write_text(
            json.dumps([{"name": "t-old", "rotated_at": "2026-05-01T00:00:00Z"}]),
            encoding="utf-8")
        (root / "state" / "green-guard").mkdir(parents=True)
        (root / "state" / "green-guard" / "verdicts.jsonl").write_text(
            json.dumps({"ts": "2026-11-05T00:00:00Z", "checkpoint": "A",
                        "status": "red", "run_id": "r1"}) + "\n", encoding="utf-8")
        line, flags, freeze, hours = run_sweep(root, now)
        assert line.startswith("SWEEP ") and "токены" in line, line
        assert "токены-возраст" in flags and "краснота-часы" in flags, flags
        assert freeze is True and hours > FREEZE_HOURS  # 2026-11-05 → 2026-11-09 12:00 > 72 ч
        assert line.count("|") == 9, line  # 7 пунктов + флаги + заморозка
        persist(root, line, freeze, hours, now)
        assert (root / "state" / "freeze" / "active.json").exists()
        # корень без state/ — тоже норма: все пункты «нет данных», заморозки нет
        empty, eflags, efreeze, _ = run_sweep(root / "no-state", now)
        assert "нет данных" in empty and not eflags and not efreeze
    print("selftest: OK (7 пунктов, флаги, заморозка >72 ч и снятие, пустое состояние)")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly-свип календаря организма (issue 13)")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--no-persist", action="store_true",
                    help="не писать state/sweep/log.jsonl и state/freeze/active.json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    now = datetime.now(timezone.utc)
    line, _flags, freeze, hours = run_sweep(Path(args.repo_root), now)
    print(line)
    if not args.no_persist:
        persist(Path(args.repo_root), line, freeze, hours, now)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
