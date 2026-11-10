#!/usr/bin/env python3
"""НОУС · тренд-радар (ADR-0017) — пульс мировых практик.

Организм обязан «идти впереди их всех» (мандат владельца): для этого он
МЕХАНИЧЕСКИ, еженедельно, снимает показания с фиксированного списка
первоисточников и фиксирует факт «мир сдвинулся». Никакой интерпретации
внутри радара: только сырые факты (теги, даты, заголовки). Превращение
сигнала в работу — тикет (задача человека и роя, не скрипта).

Только stdlib. Токен — из окружения, в файлы не пишется (ADR-0012).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

API_BASE = os.environ.get("GH_API", "https://api.github.com")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
REPO = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY") or ""

# Фиксированный список первоисточников. Расширение списка — правка кода
# через ADR (источник без ADR — это источник, который никто не заказывал).
SOURCES: list[dict] = [
    {"id": "slsa", "kind": "gh_release", "repo": "slsa-framework/slsa-github-generator"},
    {"id": "scorecard", "kind": "gh_release", "repo": "ossf/scorecard"},
    {"id": "agents-md", "kind": "gh_commit", "repo": "agentsmd/agents.md"},
    {"id": "actions-runner", "kind": "gh_release", "repo": "actions/runner"},
    {
        "id": "gh-changelog",
        "kind": "atom",
        "url": "https://github.blog/changelog/all.atom",
        "n": 5,
    },
]


def _http(url: str, accept: str = "application/vnd.github+json") -> bytes:
    """GET c одним ретраем: внешний мир флёрнит — разовый 404/5xx не должен
    ни краснить прогон, ни изображать «сдвиг мира». Повторный отказ — честный
    отказ с URL (A2)."""
    import time
    import urllib.error

    last: Exception | None = None
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"Accept": accept})
            if TOKEN and url.startswith(API_BASE):
                req.add_header("Authorization", f"Bearer {TOKEN}")
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            last = exc
            if attempt == 1:
                time.sleep(3)
    raise RuntimeError(f"источник недоступен ({url}): {last}") from last


def fetch_fact(source: dict) -> dict:
    """Один источник → один сырой факт. Падение источника — честный отказ
    с именем источника (A2: не врать о причине)."""
    kind = source["kind"]
    if kind == "gh_release":
        data = json.loads(_http(f"{API_BASE}/repos/{source['repo']}/releases/latest"))
        return {"tag": data.get("tag_name"), "published_at": data.get("published_at")}
    if kind == "gh_commit":
        data = json.loads(_http(f"{API_BASE}/repos/{source['repo']}/commits?per_page=1"))
        first = data[0]
        return {
            "sha": (first.get("sha") or "")[:12],
            "date": first["commit"]["committer"]["date"],
            "message": (first["commit"]["message"] or "").splitlines()[0][:120],
        }
    if kind == "atom":
        xml = _http(source["url"], accept="application/atom+xml")
        root = ET.fromstring(xml)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        items = []
        for entry in root.findall("a:entry", ns)[: source.get("n", 5)]:
            title = entry.findtext("a:title", default="", namespaces=ns).strip()
            updated = entry.findtext("a:updated", default="", namespaces=ns)
            items.append({"title": title, "updated": updated})
        return {"items": items}
    raise ValueError(f"неизвестный вид источника: {kind}")


def fetch_all(sources: list[dict], fetcher=fetch_fact) -> dict:
    return {s["id"]: fetcher(s) for s in sources}


def fingerprint(facts: dict) -> str:
    canonical = json.dumps(facts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_state(path: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    try:
        return json.loads(open(path, encoding="utf-8").read())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"3 state-файл битый ({path}): {exc}")


def compare(prev: dict | None, facts: dict) -> dict:
    """Чистая функция решения: first-run / stable / moved."""
    if prev is None:
        return {"mode": "first-run", "signals": []}
    prev_facts = prev.get("facts", {})
    signals = []
    for s in SOURCES:
        sid = s["id"]
        if prev_facts.get(sid) != facts.get(sid):
            signals.append(
                {
                    "id": sid,
                    "old": prev_facts.get(sid),
                    "new": facts.get(sid),
                }
            )
    return {"mode": "moved" if signals else "stable", "signals": signals}


def render_report(known: dict, state_path: str) -> str:
    lines = [
        "## ТРЕНД-РАДАР — показания мировых практик",
        "",
        f"Режим: **{known['mode']}**; сигнал-файл: `state/trend-radar.json`",
        "",
        "| Источник | Показание |",
        "|---|---|",
    ]
    for s in SOURCES:
        fact = known["facts"].get(s["id"])
        if not fact:
            lines.append(f"| {s['id']} | (нет показания) |")
        elif "tag" in fact:
            lines.append(f"| {s['id']} | релиз `{fact['tag']}` ({fact.get('published_at', '?')}) |")
        elif "sha" in fact:
            lines.append(f"| {s['id']} | коммит `{fact['sha']}` ({fact['date']}) |")
        elif "items" in fact:
            head = fact["items"][0]["title"] if fact["items"] else "—"
            lines.append(f"| {s['id']} | {len(fact['items'])} записей; свежая: {head} |")
    lines += [
        "",
        "> Радар фиксирует ТОЛЬКО сырые факты (A10: убедительность ≠ "
        "проверяемость). Интерпретация и действия — тикет, а не скрипт.",
        "",
    ]
    if known["mode"] == "moved":
        lines.append("### Сдвиги с прошлого замера")
        lines.append("")
        for sig in known["signals"]:
            lines.append(f"- **{sig['id']}**: {json.dumps(sig['old'], ensure_ascii=False)} → {json.dumps(sig['new'], ensure_ascii=False)}")
        lines.append("")
    del state_path
    return "\n".join(lines)


def issue_find_open() -> dict | None:
    """Один катящийся тред: ищем открытый issue радара (по заголовку)."""
    url = (
        f"{API_BASE}/repos/{REPO}/issues?state=open&per_page=100"
        f"&labels=trend-radar"
    )
    try:
        items = json.loads(_http(url))
    except Exception:
        return None
    for it in items:
        if "pull_request" not in it:
            return it
    return None


def issue_report(signals: list[dict], report_md: str) -> None:
    """Создать тред или дописать комментарий в существующий."""
    import urllib.error

    def post(url: str, payload: dict) -> dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())

    if not REPO:
        raise SystemExit("3 issue_report: REPO не задан")
    body = [
        "Автосигнал `scripts/trend_radar.py` (ADR-0017). Сырые факты, без интерпретации.",
        "",
        report_md,
        "",
        "---",
        "Дальше сигнал превращается в работу ТОЛЬКО через тикет "
        "(`tasks/README.md`) — таков закон организма.",
    ]
    existing = issue_find_open()
    if existing:
        post(
            f"{API_BASE}/repos/{REPO}/issues/{existing['number']}/comments",
            {"body": "\n".join(body)},
        )
        print(f"радар: комментарий в существующий тред #{existing['number']}")
    else:
        created = post(
            f"{API_BASE}/repos/{REPO}/issues",
            {
                "title": "🌍 Тренд-радар: мир сдвинулся — факты к разбору",
                "body": "\n".join(body),
                "labels": ["trend-radar"],
            },
        )
        print(f"радар: открыт тред #{created['number']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="тренд-радар НОУС (ADR-0017)")
    ap.add_argument("--state", default=os.path.join("state", "trend-radar.json"))
    ap.add_argument("--report", help="куда писать markdown-отчёт (например $GITHUB_STEP_SUMMARY)")
    ap.add_argument("--issue", action="store_true", help="открыть/дополнить тред-сигнал")
    args = ap.parse_args(argv)

    facts = fetch_all(SOURCES)
    known = {"mode": "", "signals": [], "facts": facts}
    prev = load_state(args.state)
    verdict = compare(prev, facts)
    known.update(verdict)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = render_report(known, args.state)
    if args.report:
        with open(args.report, "a", encoding="utf-8") as fh:
            fh.write(report)
    print(report)

    if verdict["mode"] == "stable":
        print("радар: мир не сдвинулся — state не перезаписывается (ритм без шума)")
        return 0

    if verdict["mode"] == "moved":
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(
                {"fingerprint": fingerprint(facts), "facts": facts, "updated": now},
                fh,
                ensure_ascii=False,
                indent=2,
            )
            fh.write("\n")
        if args.issue:
            issue_report(verdict["signals"], report)
    else:
        # first-run: пишем базу показаний, тред не заводим — сигнала ещё нет
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(
                {"fingerprint": fingerprint(facts), "facts": facts, "updated": now},
                fh,
                ensure_ascii=False,
                indent=2,
            )
            fh.write("\n")
        print("радар: first-run — база показаний записана")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
