#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 18 — страж инвентаря святого.

Читает sacred/INVENTORY.yaml (минимальный чтатель плоского YAML) и проверяет,
не касается ли мутация святого объекта. Касание = код 42 с печатью id записи.
Режимы: --lint (схема записей), --check (мутация против инвентаря), --selftest
(три подложных кейса + human_override). human_override — только ручной шаг
Хозяина. Только stdlib, Python 3.11.
"""

from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path

TIERS = {"restricted", "confidential", "internal"}
REQUIRED = ("id", "kind", "owner", "why", "tier", "guard")


def parse_inventory(text: str) -> list[dict]:
    records: list[dict] = []
    cur: dict | None = None
    inside = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            inside = line.strip() == "inventory:"
            if not inside:
                cur = None
            continue
        if not inside:
            continue
        s = line.strip()
        if s.startswith("- "):
            cur = {}
            records.append(cur)
            s = s[2:].strip()
            if not s:
                continue
        elif cur is None:
            continue
        key, _, val = s.partition(":")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1].strip()
        if val.startswith("[") and val.endswith("]"):
            cur[key.strip()] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
        elif val in ("", "null", "~"):
            cur[key.strip()] = None
        else:
            cur[key.strip()] = val
    return records


def lint(records: list[dict]) -> int:
    ids: set[str] = set()
    rc = 0
    for r in records:
        rid = str(r.get("id", "?"))
        missing = [k for k in REQUIRED if not r.get(k)]
        if missing:
            print(f"LINT: {rid}: пусты поля {', '.join(missing)}")
            rc = 2
            continue
        if rid in ids:
            print(f"LINT: {rid}: дубликат id")
            rc = 2
        ids.add(rid)
        if r["tier"] not in TIERS:
            print(f"LINT: {rid}: неизвестный tier «{r['tier']}»")
            rc = 2
        if not isinstance(r["guard"], list) or not r["guard"]:
            print(f"LINT: {rid}: guard должен быть непустым списком")
            rc = 2
        if r["kind"] in ("path", "ref-pattern") and not r.get("pattern"):
            print(f"WARN: {rid}: pattern не задан — страж пока не матчит эту запись")
    if rc == 0:
        print(f"lint: OK, записей: {len(records)}")
    return rc


def touches(rec: dict, repo: str | None, paths: list[str], refs: list[str]) -> str | None:
    kind = rec.get("kind")
    if kind == "repo":
        rid = str(rec["id"])
        if repo and (repo == rid or repo.endswith("/" + rid)):
            return f"репо {repo} — запись kind: repo"
        return None
    pattern = rec.get("pattern")
    if not pattern:
        return None
    if kind == "ref-pattern":
        for ref in refs:
            if fnmatch.fnmatch(ref, str(pattern)):
                return f"ref {ref} под «{pattern}»"
        return None
    for p in paths:
        if fnmatch.fnmatch(p, str(pattern)):
            return f"путь {p} под «{pattern}»"
    return None


def check(records: list[dict], event: str, repo: str | None, paths: list[str],
          refs: list[str], override: str | None) -> int:
    rc = 0
    for rec in records:
        how = touches(rec, repo, paths, refs)
        if not how:
            continue
        if event == "delete" and "no-delete" not in rec["guard"]:
            continue
        if event in ("push", "pull_request") and "no-push" not in rec["guard"]:
            continue
        if override == "human_override":
            print(f"SACRED-WARN: {rec['id']} затронут ({how}) под human_override — "
                  "ответственность на Хозяине")
            continue
        print(f"SACRED 42: {rec['id']} — святой объект (tier {rec['tier']}), "
              f"касание запрещено: {how}")
        rc = 42
    if rc == 0:
        print("sacred: нарушений нет")
    return rc


def selftest() -> int:
    inv = [
        {"id": "media-vault", "kind": "repo", "owner": "Хозяин", "why": "личный архив",
         "tier": "restricted",
         "guard": ["no-push", "no-delete", "no-rename", "no-automation"],
         "exception": None},
        {"id": "tags-v-star", "kind": "ref-pattern", "owner": "Хозяин",
         "why": "релизы СВЯТОЕ", "tier": "restricted",
         "guard": ["no-push", "no-delete", "no-rename", "no-automation"],
         "exception": None, "pattern": "refs/tags/v*"},
        {"id": "dependabot-branches", "kind": "ref-pattern", "owner": "Хозяин",
         "why": "чужие ветки", "tier": "internal",
         "guard": ["no-push", "no-delete", "no-automation"],
         "exception": None, "pattern": "refs/heads/dependabot/*"},
    ]
    assert lint(inv) == 0
    # кейс 1: пуш в dependabot-ветку
    assert check(inv, "push", "rtynbirf/nous", [], ["refs/heads/dependabot/pip-1"], None) == 42
    # кейс 2: удаление тега v*
    assert check(inv, "delete", "rtynbirf/nous", [], ["refs/tags/v1.2.3"], None) == 42
    # кейс 3: запись в media-vault
    assert check(inv, "push", "media-vault", ["media/big.bin"], [], None) == 42
    # human_override проходит
    assert check(inv, "push", "media-vault", ["media/big.bin"], [], "human_override") == 0
    # чужое — не матчится
    assert check(inv, "push", "rtynbirf/nous", ["src/app.py"], [], None) == 0
    print("selftest: OK (dependabot, тег v*, media-vault → 42; human_override проходит; "
          "чужое проходит)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Страж инвентаря святого (issue 18)")
    ap.add_argument("--inventory", default="sacred/INVENTORY.yaml")
    ap.add_argument("--lint", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--event", choices=["push", "pull_request", "delete"], default="push")
    ap.add_argument("--repo")
    ap.add_argument("--paths", nargs="*", default=[])
    ap.add_argument("--refs", nargs="*", default=[])
    ap.add_argument("--override", choices=["none", "human_override"], default="none")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    inv_path = Path(args.inventory)
    records = parse_inventory(inv_path.read_text(encoding="utf-8")) if inv_path.exists() else []
    if args.lint:
        return lint(records)
    if args.check:
        override = None if args.override == "none" else args.override
        return check(records, args.event, args.repo, args.paths, args.refs, override)
    ap.error("укажите --lint, --check или --selftest")


if __name__ == "__main__":
    raise SystemExit(main())
