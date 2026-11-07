# Референс: runtime-harness MVA-H

Исполняемое ядро enforcement-контура (ADR-0014). Промпт задаёт протокол;
harness обеспечивает его исполнение. LLM не входит в TCB: решения гейта
считает код, доказательства — журнал и файловая система, нарратив модели
не доверяется.

- Родословная: [ADR-0011](../decisions/0011-evidence-ledger.md) (журнал
  доказательств), [evidence-протокол](../spec/singularis/evidence-protocol.md),
  [ADR-0013](../decisions/0013-singularis-adoption.md), тикеты 0010/0011,
  [ADR-0014](../decisions/0014-runtime-harness-mvah.md).
- Территория: `src/runtime/harness/` (обзор —
  [src/runtime/README.md](https://github.com/rtynbirf/nous/blob/main/src/runtime/README.md)).

## ABI (машинная сторона)

| Объект | Контракт |
|---|---|
| `ReceiptLog(path, head_path).mint(**fields)` | append-запись `{rid, ts, prev, ...}`; единственный писатель — harness |
| `ReceiptLog.verify_chain()` | `(ok, detail)`: prev-цепь + сверка внешнего якоря `.head` |
| `Governor(ws, grants, max_calls, max_seconds).decide(action)` | `ALLOW \| DENY \| ASK` по грантам, realpath-scope, бюджетам, interrupt |
| `ToolBox(ws, log, gov).execute(action_id, tool, op, args)` | fs/exec под гейтом; receipt на каждое действие, включая отказ |
| `Auditor(log).audit(claims)` | вердикт по каждому claim: OK / FABRICATION / MISREPORT |
| `run_plan(plan, box)` | исполнение плана через гейт; компенсация на отказе — тоже с receipt |
| `make_report(ws, log, executed, claims)` | отчёт: целость цепи, вердикты, fabrication_rate |
| `to_evidence_entry(rec, run_id, subject_id)` | маппинг receipt → `schemas/evidence-entry.schema.json` |

## Формат receipt

Каждая запись — одна строка JSONL; канонический хеш тот же, что в
`src/lib/ledger.sh` (sort_keys + компактный JSON → sha256), genesis `0`*64:

```json
{"action_id":"A1","args_hash":"9f2c…","kind":"ACTION","op":"write","prev":"0…",
 "output_hash":"5d1b…","path":"nonce.txt","rid":"R0002","size":29,"status":"OK",
 "tool":"fs","ts":1762340000.123}
```

Правка любой старой записи ломает цепь `prev`; правка последней записи
ломает якорь `.head` (файл вне досягаемости модели; в проде — HMAC/подпись).

## Маппинг на EvidenceEntry

`to_evidence_entry()` заполняет обязательные поля схемы
`evidence-entry.schema.json`: `evidence_id=rid`, `timestamp` (ISO-8601 UTC),
`type` (kind записи: ACTION→intermediate, REPORT→final,
VERIFIER→verifier_decision), `claim` (из reason/или механическая сводка
`tool.op -> status`), `hash=sha256(канонический JSON receipt)`,
`prev_hash=rec.prev`, `actions[].op="tool.op"` с hash выхода. Записи отказов
несут `verifier_decision` (ACCEPT/REJECT/ESCALATE) — вердикт верификатора
попадает в тот же журнал, как требует evidence-протокол.

## Запуск

```bash
python3 -m unittest discover -s tests            # иммунитет: tests/test_harness.py
python3 src/runtime/harness/confession_test.py   # живой прогон 7 фаз; --out DIR (вне репо)
```

Фазы Confession Test: A honest (fabrication_rate=0, кросс-канальный хеш) ·
B simulant (3 фабрикации пойманы) · C partial (дельта 2/3, компенсация) ·
D scope (относительный и symlink-эскейп DENY) · G budget (третье действие
отклонено механически) · F reset (LOST→RECOVERED, hash-сверка с миром) ·
E tamper (переписанная запись ломает цепь → поймана).

## Честные границы

- В confession-фазах агент сценарный: испытывается enforcement-слой;
  real-LLM адаптер — тикет 0010, не выполнено в v0.1.
- exec не ограничен seccomp/сетевыми политиками — прод-контур требует sandbox.
- Инструмент может лгать сам (supply chain) — доверие tools вне периметра v0.1.
