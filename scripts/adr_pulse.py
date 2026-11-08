#!/usr/bin/env python3
"""adr-pulse — конвейер ADR роя (Волна ×3, W3-C1; issue rtynbirf/nous#19).

Канон (MADR-совместимая шапка; файл adr/NNNN-имя.md):

    # ADR-NNNN: Название решения
    Статус: proposed | accepted | deprecated | superseded | rejected
    Дата: ГГГГ-ММ-ДД
    Связи: supersedes=NNNN; superseded-by=NNNN; related=NNNN,NNNN   (пусто — «—»)

Правила линтера:
  1) имя файла NNNN-имя.md, номер NNNN уникален;
  2) статус обязателен и из канонического множества;
  3) дата обязательна (ГГГГ-ММ-ДД); номера монотонны: по возрастанию номера
     даты не убывают — история решений читается diff-ом;
  4) у superseded заполнен superseded-by на существующий номер;
  5) у rejected есть строка «отвергая — предлагаю» (мост к журналу отвержений, №20);
  6) все ссылки указывают на существующие ADR, superseded-by — не на себя.

Новые решения входят через статус proposed и живут в нём до приёмки Хозяином.
Принятые ADR не переписываются — только superseded_by.

Режимы (каталог передаётся аргументом — скрипт репо-агностичен):
  lint <dir>         отчёт «номер · имя · статус · дата · связи»; код 1 при нарушении
  index <dir>        перегенерировать <dir>/INDEX.md (детерминированно)
  check-index <dir>  код 1, если INDEX.md на диске отличается от регенерации
Только stdlib, Python 3.11.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

STATUSES = ("proposed", "accepted", "deprecated", "superseded", "rejected")
FILE_RE = re.compile(r"^(\d{4})-.+\.md$")
TITLE_RE = re.compile(r"^#\s*ADR-(\d{4}):\s*(.+?)\s*$", re.M)
STATUS_RE = re.compile(r"^Статус:[ \t]*(\S+)[ \t]*$", re.M)
DATE_RE = re.compile(r"^Дата:[ \t]*(\d{4}-\d{2}-\d{2})[ \t]*$", re.M)
LINKS_RE = re.compile(r"^Связи:[ \t]*(\S.*)?$", re.M)
BRIDGE = "отвергая — предлагаю"
LINK_KINDS = ("supersedes", "superseded-by", "related")


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    num = FILE_RE.match(path.name)
    status = STATUS_RE.search(text)
    date = DATE_RE.search(text)
    links = {k: [] for k in LINK_KINDS}
    problems = []
    lm = LINKS_RE.search(text)
    if lm is None:
        problems.append("нет строки «Связи:» (пустые связи — «Связи: —»)")
    else:
        for part in (lm.group(1) or "").split(";"):
            part = part.strip()
            if not part or part == "—":
                continue
            if "=" not in part:
                problems.append(f"связь без «=»: «{part}»")
                continue
            key, _, val = part.partition("=")
            key = key.strip()
            targets = [v.strip() for v in val.split(",") if v.strip() and v.strip() != "—"]
            if key in links:
                links[key] = targets
            else:
                problems.append(f"неизвестный вид связи «{key}» (канон: {', '.join(LINK_KINDS)})")
    title = TITLE_RE.search(text)
    return {"file": path.name, "text": text,
            "number": num.group(1) if num else None,
            "name": title.group(2) if title else path.stem,
            "status": status.group(1) if status else None,
            "date": date.group(1) if date else None,
            "links": links, "problems": problems}


def load(directory: str) -> list[dict]:
    d = Path(directory)
    if not d.is_dir():
        return []
    return [parse(p) for p in sorted(d.glob("*.md")) if p.name != "INDEX.md"]


def links_cell(c: dict) -> str:
    return "; ".join(f"{k}={','.join(c['links'][k]) or '—'}" for k in LINK_KINDS)


def lint(directory: str) -> int:
    cards = load(directory)
    if not cards and not Path(directory).is_dir():
        print(f"Каталог {directory} отсутствует — гейт ADR в спящем режиме (нулевой ADR).")
        return 0
    errors: list[str] = []
    by_num: dict[str, list[str]] = {}
    for c in cards:
        if c["number"] is None:
            errors.append(f"{c['file']}: имя не по канону NNNN-имя.md")
        else:
            by_num.setdefault(c["number"], []).append(c["file"])
        errors += [f"{c['file']}: {p}" for p in c["problems"]]
    for number, files in sorted(by_num.items()):
        if len(files) > 1:
            errors.append(f"дубликат номера {number}: {', '.join(files)}")
    known = set(by_num)
    for c in cards:
        f = c["file"]
        if c["status"] is None:
            errors.append(f"{f}: нет «Статус:»")
        elif c["status"] not in STATUSES:
            errors.append(f"{f}: статус «{c['status']}» вне канона ({', '.join(STATUSES)})")
        if c["date"] is None:
            errors.append(f"{f}: нет «Дата: ГГГГ-ММ-ДД»")
        if c["status"] == "superseded" and not c["links"]["superseded-by"]:
            errors.append(f"{f}: superseded без superseded-by")
        if c["status"] == "rejected" and BRIDGE not in c["text"]:
            errors.append(f"{f}: rejected без строки «{BRIDGE}»")
        for kind, targets in c["links"].items():
            for t in targets:
                if t not in known:
                    errors.append(f"{f}: {kind} → {t}: такого ADR нет в каталоге")
                elif kind == "superseded-by" and t == c["number"]:
                    errors.append(f"{f}: superseded-by указывает на самого себя")
    dated = sorted((c for c in cards if c["number"] and c["date"]), key=lambda c: c["number"])
    for a, b in zip(dated, dated[1:]):
        if a["number"] != b["number"] and b["date"] < a["date"]:
            errors.append(f"монотонность: {b['file']} (№{b['number']}, {b['date']}) старше "
                          f"{a['file']} (№{a['number']}, {a['date']})")
    print(f"adr-pulse · каталог {directory} · ADR: {len(cards)}")
    for c in sorted(cards, key=lambda c: (c["number"] or "9999", c["file"])):
        print(f"{c['number'] or '????'} · {c['name']} · {c['status'] or 'НЕТ СТАТУСА'} · "
              f"{c['date'] or '—'} · {links_cell(c)}")
    for e in errors:
        print(f"ОШИБКА: {e}")
    print("итог: FAIL — канон нарушен" if errors else "итог: OK — канон соблюдён")
    return 1 if errors else 0


def render_index(directory: str) -> str:
    cards = load(directory)
    lines = [f"<!-- автогенерация: python3 scripts/adr_pulse.py index {directory} — руками не править -->",
             "", "# Индекс ADR (adr-pulse)", "",
             "Канон и гейт: scripts/adr_pulse.py (issue rtynbirf/nous#19).",
             "Новые решения входят через `proposed`; принятые не переписываются — только superseded_by.", "",
             "| Номер | Имя | Статус | Дата | Связи |", "|---|---|---|---|---|"]
    rows = [c for c in cards if c["number"]]
    if rows:
        lines += [f"| {c['number']} | {c['name']} | {c['status'] or '—'} | {c['date'] or '—'} | "
                  f"{links_cell(c)} |" for c in sorted(rows, key=lambda c: c["number"])]
    else:
        lines.append("| — | (заполняется скриптом при первом прогоне) | — | — | — |")
    return "\n".join(lines) + "\n"


def check_index(directory: str) -> int:
    fresh = render_index(directory)
    target = Path(directory) / "INDEX.md"
    if not target.is_file():
        print(f"ОШИБКА: {target} отсутствует — запустите: python3 scripts/adr_pulse.py index {directory}")
        return 1
    if target.read_text(encoding="utf-8") != fresh:
        print(f"ОШИБКА: {target} протух — отличается от регенерации (индекс не может протухнуть).")
        return 1
    print(f"{target} свежий: побайтово равен регенерации.")
    return 0


def main(argv: list[str]) -> int:
    modes = {"lint": lint, "check-index": check_index}
    if len(argv) not in (2, 3) or argv[1] not in ("lint", "index", "check-index"):
        print(__doc__)
        return 2
    directory = argv[2] if len(argv) == 3 else "adr"
    if argv[1] == "index":
        target = Path(directory) / "INDEX.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_index(directory), encoding="utf-8")
        print(f"перегенерирован {target}")
        return 0
    return modes[argv[1]](directory)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
