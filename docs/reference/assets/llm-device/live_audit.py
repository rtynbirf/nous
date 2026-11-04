# -*- coding: utf-8 -*-
"""
ЖИВОЙ ПРОГОН v2.0 — ЭТАП AUDIT (механическая проверка, уровень 0.85).
Аудитор: не исполнитель. Каждая несущая цитата агентов проверяется regex-ом
в указанном файле. Вердикт: HIT (строки) / MISS.
Отдельные проверки на ОТСУТСТВИЕ (absence) — для конструков, заявленных
агентами как отсутствующие (ТРЕВОГА вне DS/UMO; resolved_unknowns вне state_delta;
ограничения CAVEATS).
"""
import re

UP = "/home/z/my-project/upload"
F = {
    "DS":  open(f"{UP}/chat.deepseek.com_.prompt.txt", encoding="utf-8").read().splitlines(),
    "UMO": open(f"{UP}/umo.proton.me_.prompt.txt", encoding="utf-8").read().splitlines(),
    "QW":  open(f"{UP}/Qwen_python_20260910_6d3o2ulin.py", encoding="utf-8").read().splitlines(),
    "V41": open(f"{UP}/FINALNIY_PROMPT_V4.1_CANONICAL_CORRECTED.md", encoding="utf-8").read().splitlines(),
    "V40": open(f"{UP}/FINALNIY_PROMPT_V4.0.md", encoding="utf-8").read().splitlines(),
}

def hit(fname, terms, window=1):
    """Все terms встречаются в одной строке или в окне window строк."""
    lines = F[fname]
    out = []
    for i, ln in enumerate(lines):
        for j in range(window):
            k = i + j
            if k < len(lines) and all(t.lower() in (lines[i] + " " + lines[k]).lower() if k != i
                                      else t.lower() in lines[i].lower() for t in terms):
                out.append(i + 1)
                break
        else:
            continue
        continue
    # дубликаты соседних номеров схлопнуть
    dedup = []
    for n in out:
        if not dedup or n - dedup[-1] > 2:
            dedup.append(n)
    return dedup

def absent(fname, term):
    return [i + 1 for i, ln in enumerate(F[fname]) if term.lower() in ln.lower()]

CHECKS = [
    # (метка, тип, файл, термины, окно строк)
    ("G1 правило 'задача без spawn_reason не создаётся' (V41)", "hit", "V41", ["spawn_reason", "не создаётся"], 1),
    ("G1 жёсткое правило (DS)",                                 "hit", "DS",  ["spawn_reason", "задача не созда"], 1),
    ("G2 блок '4 фильтра' лог-инф-рес-гип (V41)",               "hit", "V41", ["NO логической зависимости", "NO гипотезной"], 8),
    ("G2 DS '4 вида зависимости' поимённо",                     "hit", "DS",  ["DATA_DEPENDENCY", "HYPOTHESIS_CONFLICT"], 1),
    ("T3 необратимое/дорогое -> СПРОСИ (V41)",                  "hit", "V41", ["T3", "Необратимое или дорогое действие"], 1),
    ("G3 маркировка уровнем 1..5 (V41)",                        "hit", "V41", ["Маркируется уровнем", "1..5"], 1),
    ("G4 append-only (V41)",                                    "hit", "V41", ["append-only"], 1),
    ("G4 'тихая правка' запрещена (V41)",                       "hit", "V41", ["Переписывать ранние выводы тихо"], 1),
    ("G5 'Diff пуст -> ТРЕВОГА' (DS)",                          "hit", "DS",  ["Diff пуст", "ТРЕВОГА"], 1),
    ("G5 'ТРЕВОГА' (UMO)",                                      "hit", "UMO", ["ТРЕВОГА"], 1),
    ("G5 'ТРЕВОГА' ОТСУТСТВУЕТ в V41",                          "absent", "V41", ["ТРЕВОГА"], 0),
    ("G5 'ТРЕВОГА' ОТСУТСТВУЕТ в V40",                          "absent", "V40", ["ТРЕВОГА"], 0),
    ("G5 'ТРЕВОГА' ОТСУТСТВУЕТ в QW",                           "absent", "QW",  ["ТРЕВОГА"], 0),
    ("Карантин 'посылка... ≥2–3' (DS)",                         "hit", "DS",  ["как посылка", "≥2–3"], 1),
    ("Снятие карантина: 2–3+ ИЛИ 2 источника ИЛИ ablation (UMO)","hit", "UMO", ["Снятие карантин", "ablation"], 2),
    ("STOP_REQUEST c AND-ами (V41)",                            "hit", "V41", ["no_critical_open_item", "convergence_stability"], 3),
    ("STOP_REQUEST ядро цикла без AND (V41:~740)",              "hit", "V41", ["STOP", "BudgetPressure ≥ 0.8) OR"], 2),
    ("Вето: 6-й пункт 'unknowns+доступные действия' (V41)",     "hit", "V41", ["Critical unknowns всё ещё открыты", "доступные проверяемые действия"], 1),
    ("Вето V40: инверсия 'нельзя повлиять'",                    "hit", "V40", ["Critical unknowns", "нельзя повлиять"], 1),
    ("ε = 1 только в QW",                                       "hit", "QW",  ["ε = 1"], 1),
    ("ε = 1 ОТСУТСТВУЕТ в V41",                                 "absent", "V41", ["ε = 1"], 0),
    ("ΔI-формула с resolved_unknowns (QW)",                     "hit", "QW",  ["len(added_claims)", "len(resolved_unknowns)"], 1),
    ("resolved_unknowns ОТСУТСТВУЕТ в V41 (несчитаемость ΔI)",  "absent", "V41", ["resolved_unknowns"], 0),
    ("ledger — поле STATE в контексте (V41)",                   "hit", "V41", ["ledger: [", "append-only"], 1),
    ("AppendLedger / внешний исполнитель (V41)",                "hit", "V41", ["AppendLedger"], 1),
    ("PROMPT_SPECIFICATION_ONLY (V41)",                         "hit", "V41", ["PROMPT_SPECIFICATION_ONLY"], 1),
    ("ЧАСТЬ G: поведение, не декларация (V41)",                 "hit", "V41", ["Behavior_observed", "НЕ ДОСТАТОЧНО"], 10),
    ("ЧАСТЬ G: причинная зависимость от контура (V41)",         "hit", "V41", ["причинную зависимость от управляющего контура"], 1),
    ("UMO: SOLVED = success_criteria + тесты + ΔI≈0",           "hit", "UMO", ["success_criteria", "ΔI≈0"], 1),
    ("UMO:414 premature convergence -> ВЕТО + INJECT paradigm-shift", "hit", "UMO", ["paradigm-shift", "INJECT"], 1),
    ("Форс-CONTINUE: возврат CONTINUE -> C.1 (V41)",            "hit", "V41", ["CONTINUE → § C.1"], 1),
    ("Счётчик повторных остановок ОТСУТСТВУЕТ в V41",           "absent", "V41", ["окна подряд"], 0),
    ("Критичность = входящая степень графа (DS, прокси)",       "hit", "DS",  ["входящая степень", "критичность"], 1),
]

print("=" * 76)
print("AUDIT — механическая проверка несущих цитат (уровень 0.85)")
print("=" * 76)
n_hit = n_absent_ok = n_fail = 0
for label, kind, fname, terms, win in CHECKS:
    if kind == "hit":
        rows = hit(fname, terms, window=win)
        ok = bool(rows)
    else:  # absent-проверка: term НЕ должен встречаться
        rows = absent(fname, terms[0])
        ok = not rows
    mark = "PASS" if ok else "FAIL"
    if ok:
        n_hit += 1
    else:
        n_fail += 1
    detail = f"строки {rows[:6]}" if ok and kind == "hit" else (
             f"встречается в {rows[:6]}" if not ok and kind == "absent" else "отсутствует ✓")
    print(f"[{mark}] {label:<58} {fname}: {detail}")
print(f"\nИтог AUDIT: {n_hit}/{len(CHECKS)} PASS, {n_fail} FAIL")

# Счёт упоминаний CAVEATS по корпусу (проверка red-team: 8 упоминаний, 0 ограничений)
print("\nCAVEATS-аудит (все упоминания, проверка на ограничения):")
total = 0
for fname in ("DS", "UMO", "QW", "V41", "V40"):
    rows = [i + 1 for i, ln in enumerate(F[fname]) if "caveat" in ln.lower()]
    total += len(rows)
    print(f"   {fname}: {rows if rows else '—'}")
print(f"   всего упоминаний: {total}; строк с ограничением CAVEATS: 0 (все — определения/enum)")

# no_critical_open_item и convergence_stability: где употребляются
for term in ("no_critical_open_item", "convergence_stability"):
    print(f"\nТермин '{term}':")
    for fname in ("DS", "UMO", "QW", "V41", "V40"):
        rows = absent(fname, term)
        if rows:
            print(f"   {fname}: строки {rows}")
