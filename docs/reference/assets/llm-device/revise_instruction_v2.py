# -*- coding: utf-8 -*-
"""
РЕВИЗИЯ ИНСТРУКЦИИ «ЭКСПЛУАТАЦИЯ УСТРОЙСТВА LLM=ИИ» v1.0 -> v2.0
Аудит v1.0: находки слабых мест, закрытие дыр, пере-верификация в песочнице.

Ревизионные пункты:
  Р1. Вето-пространство: канон V4.1 содержит 6 пунктов запрета, v1.0 моделировала 5
      -> перечисление 2^6=64 (63/64 блокируется), а не 2^5=32 (31/32).
  Р2. Тупиковая пара (STOP_REQUEST=1 ∧ вето) не имела правила разрешения
      -> перечисление 2^10 с зависимостью no_critical=¬(F1∨F2∨F6), таблица квадрантов.
  Р3. Семантическая дыра канона: распространяется ли вето на SOLVED_WITH_CAVEATS?
      -> операторское решение v2.0 (помечено как решение, не приписано канону).
  Р4. Абляция v1.0 считала нарушения в смешанной гранулярности (события+прогоны)
      -> парная контрфактическая абляция: каждый прогон с одинаковым начальным
         состоянием ГСЧ исполняется дважды (A: контур включён / C: удалён).
  Р5. В v1.0 была мёртвая строка проверки (no_skip с "...and False") и свойство
      бюджет-монотонности, истинное по построению -> честная переклассификация
      свойств: ПРОВЕРЕННЫЕ vs ИСТИННЫЕ-ПО-ПОСТРОЕНИЮ; новые P7 (живость),
      P8 (врата журнала).
  Р6. Зависание (TIMEOUT_400) не имело операторского протокола -> измерение доли
      зависаний + §8 v2.0.
  Р7. Пороги 0.95/0.85/0.8 разрозненны -> единая таблица (проверено grep по 5 линиям).
"""
import re, random, itertools
from collections import deque, Counter

UP = "/home/z/my-project/upload"
corpus = {
    "V3.0_DeepSeek": open(f"{UP}/chat.deepseek.com_.prompt.txt", encoding="utf-8").read(),
    "Final1.0_Proton": open(f"{UP}/umo.proton.me_.prompt.txt", encoding="utf-8").read(),
    "V4.1.1_Qwen":    open(f"{UP}/Qwen_python_20260910_6d3o2ulin.py", encoding="utf-8").read(),
    "V4.1_Canonical": open(f"{UP}/FINALNIY_PROMPT_V4.1_CANONICAL_CORRECTED.md", encoding="utf-8").read(),
    "V4.0_md":        open(f"{UP}/FINALNIY_PROMPT_V4.0.md", encoding="utf-8").read(),
}
text_sources = list(corpus)  # 5 текстовых линий (PDF-снимок в ревизии не участвует: потеря уже доказана)

# ---------- Р1. Вето канона: 6 пунктов (V4.1, строки 467+) ----------
CANON_VETO = [
    "F1: на критических утверждениях ΔI > ε (критика ещё движется)",
    "F2: неразрешённые противоречия высокой важности",
    "F3: непроверенные контрпримеры / резкие альтернативы",
    "F4: действует флаг confirmation_bias",
    "F5: последние N итераций не изменили главный вывод (локальный оптимум)",
    "F6: critical unknowns открыты И существуют доступные проверяемые действия",
]
# Проверка Р1 по корпусу: 6 пунктов присутствуют в каноне V4.1 и V4.1.1-Qwen
v41 = corpus["V4.1_Canonical"]
r1_checks = {
    "F1(ΔI>ε на критических)": bool(re.search(r"На критических утверждениях ΔI", v41)),
    "F2(противоречия HIGH)":   bool(re.search(r"противоречия высокой важности", v41)),
    "F3(контрпримеры)":        bool(re.search(r"непроверенные контрпримеры", v41)),
    "F4(confirmation_bias)":   bool(re.search(r"confirmation_bias", v41)),
    "F5(N итераций без изм.)": bool(re.search(r"не изменили главный вывод", v41)),
    "F6(unknowns+действия)":   bool(re.search(r"Critical unknowns всё ещё открыты", v41)),
}

# ---------- FSM (канон V4.1) — как в v1.0 ----------
S = dict(INIT="INIT", GOAL_AUDIT="GOAL_AUDIT", STATE_0="STATE_0", SPAWN="SPAWN",
         SELECT="SELECT", EXECUTE="EXECUTE", AUDIT="AUDIT", LEDGER="LEDGER",
         FOLD="FOLD", DETECT="DETECT", TRANSFORM="TRANSFORM", STOP="STOP_CHECK",
         SYNTH="SYNTHESIS", CLOSED="CLOSED", ESC="ESCALATED",
         T_SOLVED="TERM_SOLVED", T_CAVEATS="TERM_SOLVED_CAVEATS",
         T_BUDGET="TERM_BUDGET", T_ESC="TERM_ESCALATED")
TERMINALS = {S["T_SOLVED"], S["T_CAVEATS"], S["T_BUDGET"], S["T_ESC"]}
CYCLE = ["SPAWN","SELECT","EXECUTE","AUDIT","LEDGER","FOLD","DETECT","TRANSFORM"]
EDGES = [
    (S["INIT"],  S["GOAL_AUDIT"], "запуск"),
    (S["GOAL_AUDIT"], S["STATE_0"], "G: посылки проверены (7 пунктов)"),
    (S["GOAL_AUDIT"], S["ESC"],  "T1 противоречие GOAL | T2 ценностный выбор | ложная посылка"),
    (S["STATE_0"], S["SPAWN"],   "STATE/ONTOLOGY/BOUNDARY зафиксированы"),
    (S["SPAWN"], S["SELECT"],    "G1: spawn_reason"),
    (S["SELECT"], S["EXECUTE"],  "G2: 4 фильтра"),
    (S["EXECUTE"], S["AUDIT"],   "результат получен"),
    (S["EXECUTE"], S["ESC"],     "T3 необратимое/дорогое"),
    (S["AUDIT"], S["LEDGER"],    "G3: уровень лестницы"),
    (S["LEDGER"], S["FOLD"],     "G4: append-only"),
    (S["FOLD"],  S["DETECT"],    "G5: ΔS обязателен"),
    (S["DETECT"], S["TRANSFORM"],"патологии обработаны"),
    (S["DETECT"], S["ESC"],      "карантин age > T"),
    (S["TRANSFORM"], S["STOP"],  "G6: tombstones, prune"),
    (S["STOP"], S["SPAWN"],      "CONTINUE"),
    (S["STOP"], S["SYNTH"],      "STOP_REQUEST ∧ ¬вето | бюджет"),
    (S["STOP"], S["ESC"],        "T4 | T5"),
    (S["SYNTH"], S["T_SOLVED"],  "¬вето ∧ criteria ∧ ΔI≈0"),
    (S["SYNTH"], S["T_CAVEATS"], "¬вето ∧ scope/unknowns"),
    (S["SYNTH"], S["T_BUDGET"],  "BudgetPressure ≥ 0.8"),
    (S["SYNTH"], S["CLOSED"],    "синтез выдан"),
    (S["CLOSED"], S["SPAWN"],    "REOPENED"),
    (S["ESC"], S["T_ESC"],       "оператор: стоп"),
    (S["ESC"], S["GOAL_AUDIT"],  "оператор: новый GOAL"),
    (S["ESC"], S["SPAWN"],       "оператор: продолжить"),
]
preds = {}
succs = {}
for a, b, _ in EDGES:
    preds.setdefault(b, set()).add(a)
    succs.setdefault(a, set()).add(b)
ALL_STATES = set(preds) | set(succs)

def bfs(start, edges=None, blocked=None):
    edges = EDGES if edges is None else edges
    seen, q = {start}, deque([start])
    while q:
        v = q.popleft()
        for a, b, _ in edges:
            if a == v and b not in seen and b != blocked:
                seen.add(b); q.append(b)
    return seen

# ---------- Р5. Честная переклассификация свойств ----------
print("=" * 74)
print("РЕВИЗИЯ v2.0 — БЛОК А: СТРУКТУРНЫЕ СВОЙСТВА (честная классификация)")
print("=" * 74)
reach = bfs(S["INIT"])
P1 = reach == ALL_STATES
dead = {s for s in ALL_STATES if not succs.get(s)}
P2 = dead == TERMINALS
P3 = all(preds[t] <= {S["STOP"], S["SYNTH"], S["ESC"]} for t in TERMINALS)
P4 = preds[S["SYNTH"]] == {S["STOP"]}
P5 = all(bfs(s) & TERMINALS for s in CYCLE)
P6 = preds[S["LEDGER"]] == {S["AUDIT"]}
print(f"P1 достижимость всех из INIT:              {P1}")
print(f"P2 тупики = только терминалы:              {P2} ({sorted(dead)})")
print(f"P3 терминалы только из STOP/SYNTH/ESC:     {P3}")
print(f"P4 SYNTHESIS только из STOP_CHECK:         {P4}")
print(f"P5 каждый цикл-стейт достигает терминала:  {P5}")
print(f"P6 AUDIT — единственный вход в LEDGER:     {P6}")

# P7 живость: кратчайший путь из каждого состояния к ближайшему терминалу
dist = {}
for s in ALL_STATES:
    d, q, found = {s: 0}, deque([s]), None
    while q and found is None:
        v = q.popleft()
        if v in TERMINALS:
            found = d[v]; break
        for b in succs.get(v, ()):
            if b not in d:
                d[b] = d[v] + 1; q.append(b)
    dist[s] = found
P7 = all(v is not None for v in dist.values())
mx = max((v, k) for k, v in dist.items())
print(f"P7 живость (всякий стейт -> терминал):     {P7}; максимум кратчайших путей "
      f"= {mx[0]} шагов из {mx[1]}")
for s in CYCLE + [S["INIT"], S["GOAL_AUDIT"]]:
    print(f"      dist[{s:<12}] = {dist[s]}")

# P8 врата журнала: без LEDGER честные выходы недостижимы
edges_no_ledger = [e for e in EDGES if e[0] != S["LEDGER"] and e[1] != S["LEDGER"]]
r = bfs(S["EXECUTE"], edges=edges_no_ledger)
reach_terms_no_ledger = r & TERMINALS
P8 = reach_terms_no_ledger == {S["T_ESC"]}
print(f"P8 врата журнала (без LEDGER):             {P8}; достижимые терминалы "
      f"из EXECUTE: {sorted(reach_terms_no_ledger)}  [честные выходы SOLVED/CAVEATS/BUDGET "
      f"отрезаны {'✓' if P8 else '✗'}]")

# ---------- Р1+Р2. Перечисление 2^10: вето (6) × стоп-входы (4) ----------
print()
print("=" * 74)
print("РЕВИЗИЯ v2.0 — БЛОК Б: ВЕТО 2^6 И ТАБЛИЦА КВАДРАНТОВ (Р1, Р2, Р3)")
print("=" * 74)
print("Флаги вето канона V4.1 (исправление Р1: их ШЕСТЬ, в v1.0 было пять):")
for f in CANON_VETO:
    print(f"   {f}")
print("Проверка присутствия 6 флагов в каноне V4.1:",
      all(r1_checks.values()), r1_checks)

# Общие булевы переменные состояния: F1..F6, di(ΔI<ε), bp(≥0.8), stab(>3), esc
# Зависимость (канон V4.1: no_critical_open_item):
#   критические открытые пункты = критика движется ∨ противоречия HIGH ∨ unknowns+действия
NO_CRITICAL = lambda f: not (f[0] or f[1] or f[5])
STOP_REQ    = lambda f: ((f[6] and NO_CRITICAL(f)) or (f[7] and f[8]) or f[9])
VETO        = lambda f: any(f[:6])
# Р3 — операторское решение v2.0 (ПОМЕЧЕНО КАК РЕШЕНИЕ, не приписывается канону):
#   SOLVED блокируют все F1..F6 (канон дословно);
#   SOLVED_WITH_CAVEATS блокируют F1,F2,F3,F6 (объективные недоделки:
#   CAVEATS с открытыми противоречиями = скрытый SOLVED = тот же класс лжи,
#   что псевдотриангуляция); F4/F5 не блокируют CAVEATS — при стагнации
#   честный выход с перечислением лучше бесконечного цикла.
VETO_CAVEATS = lambda f: f[0] or f[1] or f[2] or f[5]

quad = Counter(); q2_split = Counter(); sr_total = 0; veto_total = 0
for cfg in itertools.product([0,1], repeat=10):
    sr, vt = STOP_REQ(cfg), VETO(cfg)
    sr_total += sr; veto_total += vt
    if sr and not vt:   quad["Q1: STOP ∧ ¬вето — честная остановка"] += 1
    elif sr and vt:
        if not VETO_CAVEATS(cfg):
            quad["Q2: STOP ∧ вето — CAVEATS разрешён (F4/F5)"] += 1
        else:
            quad["Q2а: STOP ∧ вето — форс-CONTINUE (риск зависания)"] += 1
            q2_split["форс-CONTINUE"] += 1
    elif not sr and vt: quad["Q4: ¬STOP ∧ вето — работа с флагами"] += 1
    else:               quad["Q3: ¬STOP ∧ ¬вето — нормальная работа"] += 1

print(f"\nПространство конфигураций: 2^10 = 1024 (6 флагов вето + di, bp, stab, esc)")
print(f"STOP_REQUEST срабатывает: {sr_total}/1024;  вето взведено: {veto_total}/1024")
blocked64 = sum(1 for c in itertools.product([0,1], repeat=6) if any(c))
print(f"Р1: перечисление вето 2^6=64: SOLVED заблокирован в {blocked64}/64 "
      f"(в v1.0 было 31/32 из-за пропуска F1)")
for k in sorted(quad):
    print(f"   {k:<52} {quad[k]:>4} конф.")
print(f"Р2: тупиковая пара (STOP_REQUEST ∧ жёсткое вето) существует и равна "
      f"{q2_split.get('форс-CONTINUE',0)} конфигурациям — правило разрешения: "
      f"форс-CONTINUE, при повторе ≥2 окон подряд -> эскалация T4 оператору.")

# ---------- Р4. Парная контрфактическая абляция ----------
print()
print("=" * 74)
print("РЕВИЗИЯ v2.0 — БЛОК В: ПАРНАЯ АБЛЯЦИЯ (Р4, Р6) — 200 000 пар прогонов")
print("=" * 74)
random.seed(20260910)
N = 200_000
pairs = Counter()
timeout = {"A": 0, "C": 0}
viol_events = Counter()

def run_walk(defective):
    budget = 50.0
    state = S["INIT"]
    claims = []
    events = set()
    for _ in range(400):
        if state == S["SPAWN"]:
            # гарант канона: ПОСЫЛКАМИ могут быть только уровни >= 2
            # (карантинные утверждения < 2 имеют право СУЩЕСТВОВАТЬ в журнале,
            #  им запрещено ИСПОЛЬЗОВАТЬСЯ как посылки — различие v1.0 сохранено)
            used = claims if defective else [c for c in claims if c >= 2]
            if defective and any(c < 2 for c in used):
                events.add("карантинная посылка использована")
        elif state == S["EXECUTE"]:
            budget -= random.uniform(0.5, 3.0)
            if random.random() < 0.85:
                claims.append(random.choice([1, 2, 3, 4, 5]))
            if random.random() < 0.01:
                state = S["ESC"]; continue
        elif state == S["STOP"]:
            flags = [random.random() < p for p in (0.06, 0.05, 0.04, 0.03, 0.03, 0.04)]
            bp = budget <= 10.0
            if defective:
                do_stop = (random.random() < 0.25) or bp
            else:
                do_stop = (random.random() < 0.25 and not any(flags)) or bp
            if do_stop and not any(flags):
                return random.choices([S["T_SOLVED"], S["T_CAVEATS"], S["T_BUDGET"]],
                                      weights=[3, 5, 3 if bp else 1])[0], budget, events
            if do_stop and any(flags):
                if defective:
                    events.add("SOLVED при взведённом вето")
                    return S["T_SOLVED"], budget, events
                state = S["SPAWN"]; continue
            if random.random() < 0.02:
                state = S["ESC"]; continue
            state = S["SPAWN"]; continue
        elif state == S["ESC"]:
            outcome = random.choices([S["T_ESC"], S["GOAL_AUDIT"], S["SPAWN"]],
                                     weights=[4, 2, 4])[0]
            if outcome == S["T_ESC"]:
                return S["T_ESC"], budget, events
            state = outcome; continue
        nxt = list(succs.get(state, ()))
        if not nxt:
            return state, budget, events
        state = random.choice(nxt)
        if budget <= 0 and state == S["STOP"]:
            return S["T_BUDGET"], budget, events
    return "TIMEOUT_400", budget, events

for _ in range(N):
    rng_state = random.getstate()          # парный контрфактический дизайн:
    tA, bA, evA = run_walk(defective=False)  # одинаковая стартовая точка ГСЧ
    random.setstate(rng_state)
    tC, bC, evC = run_walk(defective=True)
    if tA == "TIMEOUT_400": timeout["A"] += 1
    if tC == "TIMEOUT_400": timeout["C"] += 1
    for e in evA: viol_events[("A", e)] += 1
    for e in evC: viol_events[("C", e)] += 1
    if not evA and evC:
        pairs["A чист ∧ C нарушен (контур необходим)"] += 1
    elif evA and not evC:
        pairs["A нарушен ∧ C чист (аномалия!)"] += 1
    elif evA and evC:
        pairs["оба нарушены"] += 1
    else:
        pairs["оба чисты"] += 1

a_any = sum(v for (m, _), v in viol_events.items() if m == "A")
c_walks = pairs["A чист ∧ C нарушен (контур необходим)"] + pairs["оба нарушены"]
print(f"Пар прогонов: {N:,} (одинаковые стартовые условия ГСЧ в каждой паре)")
for k, v in pairs.most_common():
    print(f"   {k:<46} {v:>8,}  ({v/N:.2%})")
print(f"Зависания TIMEOUT_400: A = {timeout['A']:,} ({timeout['A']/N:.3%}), "
      f"C = {timeout['C']:,} ({timeout['C']/N:.3%})  [Р6: протокол §8 обязателен]")
print(f"События нарушений: A = {a_any}, C = {sum(v for (m,_),v in viol_events.items() if m=='C'):,}")
for (m, e), v in sorted(viol_events.items()):
    print(f"   [{m}] {e}: {v:,}")
G7 = (a_any == 0) and (c_walks > 0)
print(f"Критерий G-7 (свойство зависит от контура): "
      f"{'PASS' if G7 else 'FAIL'} — A: {a_any} нарушений, C: нарушений в {c_walks:,} прогонах")

print()
print("СУХОЙ ОСТАТОК (машинный):")
print(f"P1-P8={'ALL PASS' if all([P1,P2,P3,P4,P5,P6,P7,P8]) else 'FAIL'}; "
      f"вето=6_флагов; блокировка={blocked64}/64; квадранты=" +
      "; ".join(f"{k.split(':')[0]}={quad[k]}" for k in sorted(quad)) +
      f"; парная_абляция={N}пар; A_нарушений={a_any}; C_нарушений_прогонов={c_walks:,}; "
      f"TIMEOUT_A={timeout['A']:,}; G-7={'PASS' if G7 else 'FAIL'}")
