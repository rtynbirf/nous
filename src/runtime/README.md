# src/runtime — контур исполнения субъектов

MVA-H v0.1 (Minimal Verifiable Autonomous-assistant Harness) — исполняемое
ядро enforcement-контура: **receipts + governor + auditor**. Промпт задаёт
протокол; harness обеспечивает его исполнение. LLM не входит в TCB
(trusted computing base): решения гейта считает код, доказательства —
журнал и файловая система, а не нарратив модели.

Решение: [ADR-0014](../../docs/decisions/0014-runtime-harness-mvah.md) ·
родословная: [ADR-0011](../../docs/decisions/0011-evidence-ledger.md)
(журнал доказательств),
[evidence-протокол](../../docs/spec/singularis/evidence-protocol.md)
SINGULARIS (ADR-0013), тикеты 0010/0011, «Опрос №1» о верифицируемой
автономности (2026-11).

## Состав

| Модуль | Орган | Контракт |
|---|---|---|
| `harness/receipts.py` | append-only hash-chain журнал receipts | пишет только harness; модель ссылается на `rid`; канон-хеш совместим с `src/lib/ledger.sh` |
| `harness/governor.py` | детерминированная политика | `decide(action) -> ALLOW \| DENY \| ASK`: гранты, realpath-scope, бюджеты, interrupt |
| `harness/tools.py` | доверенные обёртки fs/exec | receipt на каждое действие, включая отказ; realpath перепроверяется перед эффектом (TOCTOU) |
| `harness/loop.py` | Gated Execution Loop + Auditor | фабрикация = claim без `rid` либо rid со статусом не того класса |
| `harness/confession_test.py` | живой прогон 7 фаз | механическое обнаружение симуляции: honest/simulant/partial/scope/budget/reset/tamper |

## Запуск

```bash
python3 -m unittest discover -s tests           # иммунитет (включая tests/test_harness.py)
python3 src/runtime/harness/confession_test.py  # живой прогон 7 фаз; артефакты — вне репо (--out)
```

## Контракт LLM-стороны

Модель эмитирует только: PLAN / ACTION_REQUEST / CLAIM{rid} / REPORT / ASK.
Голые утверждения о мире без rid = FABRICATION (механически детектируется
Auditor'ом). Каждое действие — включая отказ гейта — имеет receipt; отчёт
агента проверяется сверкой rid со статусами журнала.

## Честные границы v0.1

- confession-фазы используют сценарного агента (honest/simulant персоны):
  испытуемый здесь — enforcement-слой, а не модель. Подключение real-LLM
  перед тем же ABI — следующий шаг (тикет 0010: loader + run_subject.sh).
- exec не ограничен seccomp/сетевыми политиками — прод-контур требует sandbox.
- Подмена ПОСЛЕДНЕЙ записи ловится только внешним якорем head-хеша
  (`.head` вне досягаемости модели; в проде — HMAC/подпись).
- Инструмент может лгать сам (supply chain) — доверие tools вне периметра v0.1.

Подробный референс: [docs/reference/harness.md](../../docs/reference/harness.md).
