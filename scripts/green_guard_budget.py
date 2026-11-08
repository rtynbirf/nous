#!/usr/bin/env python3
"""Волна ×3 · W3-B · issue 12 — «Зелёный страж с error budget».

Аддитивное бюджетное крыло вердикт-крона (сам крон спроектирован в карте и
живёт отдельным промптом; существующие workflows не тронуты). Закон: точка,
красная более 24 часов подряд, = инцидент. Инцидент порождается автоматически:
(1) append-строка в state/green-guard/incidents.jsonl (без дублей по серии),
(2) пост-мортем-каркас в post-mortems/, (3) burn rate 7 дней в отчёте стража.
Скрипт только читает вердикт-лог и дописывает свои файлы — историю не правит.

Формат вердикт-лога (JSONL): {"ts": "2026-11-08T06:00:00Z", "checkpoint":
"имя точки", "status": "green|red", "run_id": "id прогона"}. Файл может
отсутствовать — это норма первого прогона. Только stdlib, Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RED_AFTER_HOURS = 24.0
WINDOW_DAYS = 7
PM_NOTE = "(заполняется скриптом при первом прогоне: часы красноты, burn rate 7 дней)"
PM_TAIL = ("## Хронология\n(заполняется владельцем инцидента)\n\n"
           "## Причина и лечение\n(заполняется владельцем инцидента)\n\n"
           "## Что закрыть, чтобы не повторилось\n(заполняется владельцем инцидента)\n")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def load_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.sort(key=lambda r: (parse_ts(r["ts"]), str(r.get("checkpoint", ""))))
    return rows


def red_streaks(rows: list[dict]) -> dict[str, dict]:
    """Точка → {since, run_id} начала текущей красной серии (зелёный сбрасывает)."""
    streak: dict[str, dict] = {}
    for row in rows:
        cp = str(row.get("checkpoint", "?"))
        if str(row.get("status", "")).lower() == "red":
            streak.setdefault(cp, {"since": row["ts"], "run_id": row.get("run_id", "")})
        else:
            streak.pop(cp, None)
    return streak


def burn_rate(rows: list[dict], now: datetime) -> float | None:
    """Доля красных вердикт-строк за последние 7 дней; None — данных нет."""
    window = [r for r in rows if parse_ts(r["ts"]) >= now - timedelta(days=WINDOW_DAYS)]
    if not window:
        return None
    red = sum(1 for r in window if str(r.get("status", "")).lower() == "red")
    return red / len(window)


def slug(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_.-]+", "-", name).strip("-")
    return s or "point"


def post_mortem_text(checkpoint: str, hours: float, run_id: str, log_label: str, ts: str) -> str:
    return (f"# PM: точка «{checkpoint}» красная более {RED_AFTER_HOURS:.0f} ч\n\n"
            f"- Открыт: {ts} (UTC)\n"
            f"- Источник: вердикт-лог `{log_label}`, run_id `{run_id}`\n"
            f"- Закон: 🔴 > {RED_AFTER_HOURS:.0f} ч = инцидент (error budget, issue 12)\n"
            f"- Часы красноты на момент открытия: {hours:.1f} ч\n\n"
            f"## Факты\n{PM_NOTE}\n\n{PM_TAIL}")


def handle_incidents(streak: dict[str, dict], rows: list[dict], state_root: Path,
                     log_label: str, now: datetime) -> list[dict]:
    inc_dir = state_root / "green-guard"
    inc_dir.mkdir(parents=True, exist_ok=True)
    inc_log = inc_dir / "incidents.jsonl"
    seen: set[str] = set()
    if inc_log.exists():
        for line in inc_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(str(json.loads(line).get("streak_since", "")))
    fresh: list[dict] = []
    for cp, info in streak.items():
        hours = (now - parse_ts(info["since"])).total_seconds() / 3600.0
        if hours <= RED_AFTER_HOURS or info["since"] in seen:
            continue
        rate = burn_rate(rows, now)
        record = {"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "checkpoint": cp,
                  "red_hours": round(hours, 2), "run_id": info["run_id"],
                  "streak_since": info["since"],
                  "burn_rate_7d": None if rate is None else round(rate, 4)}
        with inc_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        pm_dir = state_root.parent / "post-mortems"
        pm_dir.mkdir(parents=True, exist_ok=True)
        pm_path = pm_dir / f"PM-{now:%Y-%m-%d}-{slug(cp)}.md"
        pm_path.write_text(post_mortem_text(cp, hours, info["run_id"], log_label,
                                            record["ts"]), encoding="utf-8")
        fresh.append(record)
    return fresh


def report(rows: list[dict], state_root: Path, log_label: str, now: datetime) -> int:
    """Печатает вердикт-строки со счётчиком часов красноты; возвращает число инцидентов."""
    rate = burn_rate(rows, now)
    rate_txt = "нет данных" if rate is None else f"{rate * 100:.1f}%"
    print(f"# Вердикт бюджета · {now:%Y-%m-%d %H:%M} UTC · burn rate {WINDOW_DAYS} д: {rate_txt}")
    if not rows:
        print("нет данных (заполняется скриптом при первом прогоне)")
        return 0
    streak = red_streaks(rows)
    last: dict[str, str] = {}
    for r in rows:
        last[str(r.get("checkpoint", "?"))] = str(r.get("status", "")).lower()
    incidents = 0
    for cp in sorted(last):
        if cp not in streak:
            print(f"{cp} 🟢 краснота 0.0 ч")
            continue
        hours = (now - parse_ts(streak[cp]["since"])).total_seconds() / 3600.0
        if hours > RED_AFTER_HOURS:
            incidents += 1
            print(f"{cp} 🔴 ИНЦИДЕНТ: красна {hours:.1f} ч (с {streak[cp]['since']})")
        else:
            print(f"{cp} 🔴 красна {hours:.1f} ч (с {streak[cp]['since']})")
    fresh = handle_incidents(streak, rows, state_root, log_label, now)
    if fresh:
        print(f"новых инцидентов: {len(fresh)} → каркасы пост-мортемов в post-mortems/")
    return incidents


def selftest() -> int:
    now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        state_root = root / "state"
        log = root / "verdicts.jsonl"
        rows = [
            {"ts": "2026-11-08T00:00:00Z", "checkpoint": "A", "status": "green", "run_id": "r1"},
            {"ts": "2026-11-08T00:00:00Z", "checkpoint": "B", "status": "red", "run_id": "r1"},
            {"ts": "2026-11-08T06:00:00Z", "checkpoint": "A", "status": "red", "run_id": "r2"},
            {"ts": "2026-11-08T06:00:00Z", "checkpoint": "B", "status": "red", "run_id": "r2"},
            {"ts": "2026-11-08T12:00:00Z", "checkpoint": "A", "status": "green", "run_id": "r3"},
        ]
        log.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        streak = red_streaks(load_log(log))
        assert set(streak) == {"B"}, streak
        assert (now - parse_ts(streak["B"]["since"])).total_seconds() / 3600.0 > RED_AFTER_HOURS
        once = handle_incidents(streak, load_log(log), state_root, "verdicts.jsonl", now)
        assert len(once) == 1 and once[0]["checkpoint"] == "B"
        assert handle_incidents(streak, load_log(log), state_root, "verdicts.jsonl", now) == []
        inc_lines = (state_root / "green-guard" / "incidents.jsonl").read_text(
            encoding="utf-8").splitlines()
        assert len(inc_lines) == 1
        pms = list((state_root.parent / "post-mortems").glob("PM-*.md"))
        assert len(pms) == 1 and "24 ч" in pms[0].read_text(encoding="utf-8")
        rate = burn_rate(load_log(log), now)
        assert rate is not None and 0.0 < rate < 1.0
        assert report(load_log(log), state_root, "verdicts.jsonl", now) == 1
    print("selftest: OK (серия >24 ч, инцидент без дублей, пост-мортем, burn rate)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Зелёный страж с error budget: часы красноты, инцидент >24 ч, burn rate (issue 12)")
    ap.add_argument("--log", default="state/green-guard/verdicts.jsonl",
                    help="вердикт-лог JSONL (ts, checkpoint, status, run_id)")
    ap.add_argument("--state-root", default="state",
                    help="каталог состояния (инциденты пишутся туда)")
    ap.add_argument("--report", action="store_true", help="сводка бюджета по живому логу")
    ap.add_argument("--strict", action="store_true", help="код 1, если есть инцидент >24 ч")
    ap.add_argument("--selftest", action="store_true", help="детерминированная самопроверка")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.report:
        ap.error("укажите --report или --selftest")
    now = datetime.now(timezone.utc)
    incidents = report(load_log(Path(args.log)), Path(args.state_root), args.log, now)
    return 1 if (args.strict and incidents) else 0


if __name__ == "__main__":
    raise SystemExit(main())
