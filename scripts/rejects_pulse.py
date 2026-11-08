#!/usr/bin/env python3
"""rejects-pulse — журнал отвержений роя (Волна ×3, W3-C1; issue rtynbirf/nous#20).

Конституция: отказ без критерия пересмотра не принимается; карточка неизменяема
(пломба sha256 в INDEX.md), пересмотр — только НОВАЯ карточка с supersedes
(старая в индексе revisitable, тело нетронуто). Орган отдельный, не ADR (№19):
ADR — архитектура, rejects — поведение роя. Карточка rejects/NNNN-имя.md:
«# Отказ NNNN · Имя» + поля «- **поле:** значение» (что отвергнуто,
факт-основание, почему, что предлагаю вместо, критерий пересмотра — пустой =
fail, статус rejected|revisitable, supersedes «—»/NNNN старше своего) +
«## Наблюдения» (append-only: дата · факт). Режимы: seed — стартовые карточки
§4 (существующие не трогает); lint — код 1 с именем файла и поля; index —
перегенерация INDEX.md с пломбами, детерминированно. Только stdlib, Python 3.11.
"""
from __future__ import annotations
import hashlib
import re
import sys
from pathlib import Path

FIELDS = ("что отвергнуто", "факт-основание", "почему", "что предлагаю вместо",
          "критерий пересмотра", "статус", "supersedes")
NUM_RE = re.compile(r"^(\d{4})-.+\.md$")
TITLE_RE = re.compile(r"^#\s*Отказ (\d{4}) · (.+?)\s*$", re.M)
FIELD_RE = re.compile(r"^- \*\*(.+?):\*\*[ \t]*(.*)$", re.M)
OBS_MARK = "## Наблюдения"
OBS = "## Наблюдения (append-only: дата · факт)\n\n(пока пусто)"
KARTA = "Дорожная карта v1.5 (ДОРОЖНАЯ_КАРТА_ЗЕЛЁНЫЙ_СИНГУЛЯР_2026-11-07), §4 «Отвергая — предлагаю»"
# четыре факта §4; имена 0001/0002 продиктованы критериями приёмки №20
SEEDS = {
    "0001-rerun-broken-yaml.md": ("Rerun порченого YAML", [
        "повторный запуск (rerun) workflow с испорченным YAML.",
        f"{KARTA}: ❌ rerun порченого YAML → ✅ диспатч.",
        "rerun не исправляет YAML — повторяется тот же битый запуск, минуты и очередь горят впустую.",
        "чинить YAML и запускать через workflow_dispatch.",
        "если появится механизм, который перед rerun валидирует YAML и не тратит минуты на заведомо битый файл, — путь возвращается на стол."]),
    "0002-empty-commits.md": ("Пустые коммиты", [
        "пустые коммиты как способ перезапустить проверки.",
        f"{KARTA}: ❌ пустые коммиты → ✅ тихие окна.",
        "коммит без изменений шумит историю и ничего не делает — запуск ради запуска.",
        "тихие окна: расписание проверок вне часов живой работы.",
        "если появится случай, который тихие окна не покрывают и для которого нет иного запуска, кроме пустого коммита, — случай фиксируется строкой наблюдения в этой карточке, и путь возвращается на стол."]),
    "0003-manual-dependabot-rerun.md": ("Ручной rerun dependabot", [
        "ручной rerun упавших проверок в PR dependabot.",
        f"{KARTA}: ❌ ручной rerun dependabot → ✅ ожидание цикла.",
        "dependabot сам пересобирает ветку по своему циклу; ручной rerun гоняет устаревшую ревизию и падает снова.",
        "ожидать ближайший цикл dependabot — свежая ревизия пересчитает проверки сама.",
        "если появится официальный механизм, при котором rerun подхватывает свежую ревизию ветки dependabot без новой ревизии, — путь возвращается на стол."]),
    "0004-beacon-bvg.md": ("Меню Маяка: пути Б, В, Г", [
        "альтернативы Б, В и Г из меню Маяка — меню закрыто путём А′ «Шифрованный Маяк».",
        f"{KARTA}: меню А/Б/В/Г закрыто путём А′; Б/В/Г отвергнуты, каждая по своей причине.",
        "Б — (индивидуальная причина вписывается из карты §4); В — (индивидуальная причина вписывается из карты §4); Г — (индивидуальная причина вписывается из карты §4).",
        "путь А′ «Шифрованный Маяк».",
        "если по любому из путей Б/В/Г в «Наблюдения» этой карточки попадёт факт (дата · наблюдение), снимающий его причину отказа, — путь возвращается на стол отдельной карточкой с supersedes: 0004."]),
}


def render_card(num: str, name: str, vals: list[str]) -> str:
    lines = [f"# Отказ {num} · {name}", ""]
    lines += [f"- **{f}:** {v}" for f, v in zip(FIELDS[:5], vals)]
    lines += ["- **статус:** rejected", "- **supersedes:** —", "", OBS, ""]
    return "\n".join(lines)

def seed(directory: str) -> int:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    for fname, (name, vals) in SEEDS.items():
        f = d / fname
        if f.exists():
            print(f"{f} существует — не тронут (append-only).")
            continue
        f.write_text(render_card(NUM_RE.match(fname).group(1), name, vals), encoding="utf-8")
        print(f"создана стартовая карточка {f}")
    return 0


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for m in FIELD_RE.finditer(text):
        fields.setdefault(m.group(1).strip().lower(), m.group(2).strip())
    title = TITLE_RE.search(text)
    return {"file": path.name, "text": text, "fields": fields,
            "number": title.group(1) if title else path.stem,
            "name": title.group(2) if title else path.stem}


def load(directory: str) -> list[dict]:
    d = Path(directory)
    if not d.is_dir():
        return []
    cards = []
    for p in sorted(d.glob("*.md")):
        if p.name == "INDEX.md":
            continue
        m = NUM_RE.match(p.name)
        c = parse(p)
        c["file_num"] = m.group(1) if m else None
        cards.append(c)
    return cards


def lint(directory: str) -> int:
    cards = load(directory)
    if not cards and not Path(directory).is_dir():
        print(f"Каталог {directory} отсутствует — журнал ещё не заложен (гейт спит).")
        print(f"Активация: python3 scripts/rejects_pulse.py seed {directory} && "
              f"python3 scripts/rejects_pulse.py index {directory} — и закоммитить.")
        return 0
    errors, by_num = [], {}
    for c in cards:
        n = c["file_num"]
        if n is None:
            errors.append(f"{c['file']}: имя не по канону NNNN-имя.md")
        else:
            by_num.setdefault(n, []).append(c["file"])
        t = TITLE_RE.search(c["text"])
        if n and t and t.group(1) != n:
            errors.append(f"{c['file']}: номер в заголовке ({t.group(1)}) ≠ номеру файла ({n})")
    for number, files in sorted(by_num.items()):
        if len(files) > 1:
            errors.append(f"дубликат номера {number}: {', '.join(files)}")
    for c in cards:
        f, n = c["file"], c["file_num"]
        for field in FIELDS:
            val = c["fields"].get(field)
            if val is None or not val.strip():
                errors.append(f"{f}: пустое поле «{field}» — отказ без выхода не принимается конституцией")
                continue
            if field == "статус" and val.strip() not in ("rejected", "revisitable"):
                errors.append(f"{f}: статус «{val.strip()}» вне канона (rejected | revisitable)")
            if field == "supersedes" and val.strip() != "—":
                s = val.strip()
                if not re.fullmatch(r"\d{4}", s):
                    errors.append(f"{f}: supersedes «{s}» не в форме NNNN")
                elif s not in by_num:
                    errors.append(f"{f}: supersedes {s} — карточки с таким номером нет")
                elif n and s >= n:
                    errors.append(f"{f}: supersedes {s} не старше своего номера {n}")
        if OBS_MARK not in c["text"]:
            errors.append(f"{f}: нет раздела «{OBS_MARK}» (append-only наблюдения)")
    print(f"rejects-pulse · каталог {directory} · карточек: {len(cards)}")
    for c in sorted(cards, key=lambda c: (c["file_num"] or "9999", c["file"])):
        crit = c["fields"].get("критерий пересмотра") or "—"
        print(f"{c['file_num'] or '????'} · {c['name']} · {c['fields'].get('статус') or 'НЕТ СТАТУСА'} · критерий: {crit[:60]}{'…' if len(crit) > 60 else ''}")
    for e in errors:
        print(f"ОШИБКА: {e}")
    print("итог: FAIL — конституция нарушена" if errors else "итог: OK — конституция соблюдена")
    return 1 if errors else 0


def render_index(directory: str) -> str:
    cards = load(directory)
    sup: dict[str, list[str]] = {}
    for c in cards:
        s = (c["fields"].get("supersedes") or "—").strip()
        if re.fullmatch(r"\d{4}", s):
            sup.setdefault(s, []).append(c["file_num"] or c["file"])

    def cell(v: str) -> str:
        return v.replace("|", "\\|").replace("\n", " ")
    lines = [f"<!-- автогенерация: python3 scripts/rejects_pulse.py index {directory} — руками не править -->",
             "", "# Журнал отвержений — индекс", "",
             "Отказ без критерия пересмотра не принимается; карточка неизменяема (пломба sha256):",
             "пересмотр — только новая карточка с supersedes (issue rtynbirf/nous#20).", "",
             "| № | Отказ | Статус | Критерий пересмотра | Supersedes | Пломба |",
             "|---|---|---|---|---|---|"]
    rows = [c for c in cards if c["file_num"]]
    if rows:
        for c in sorted(rows, key=lambda c: c["file_num"]):
            st = c["fields"].get("статус") or "—"
            if c["file_num"] in sup:
                st = "revisitable ← supersedes: " + ",".join(sorted(sup[c["file_num"]]))
            seal = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()[:12]
            crit = c["fields"].get("критерий пересмотра") or "—"
            supd = c["fields"].get("supersedes") or "—"
            lines.append(f"| {c['file_num']} | {cell(c['name'])} | {st} | {cell(crit)} | {supd} | {seal} |")
    else:
        lines.append("| — | (заполняется скриптом при первом прогоне) | — | — | — | — |")
    return "\n".join(lines) + "\n"

def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or argv[1] not in ("seed", "lint", "index"):
        print(__doc__)
        return 2
    directory = argv[2] if len(argv) == 3 else "rejects"
    if argv[1] == "seed":
        return seed(directory)
    if argv[1] == "lint":
        return lint(directory)
    target = Path(directory) / "INDEX.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_index(directory), encoding="utf-8")
    print(f"перегенерирован {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
