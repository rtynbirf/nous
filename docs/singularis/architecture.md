# Архитектура организма SINGULARIS

## Высокоуровневая схема

```
                    ┌──────────────────────┐
                    │   HUMAN OVERSIGHT    │
                    │  (high-stakes gates) │
                    └──────────┬───────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                     ORCHESTRATOR (ядро)                     │
│  - читает tasks/open/                                       │
│  - выбирает субъекта по контракту                           │
│  - запускает run с budget + checkpoint                      │
│  - требует evidence перед эффектом                          │
└──────┬───────────────────────────────┬──────────────────────┘
       │                               │
       ▼                               ▼
┌──────────────┐               ┌──────────────────┐
│   SUBJECTS   │               │    VERIFIER      │
│ (контракты)  │◄─────────────►│ (независимый)    │
└──────┬───────┘               └────────┬─────────┘
       │                                │
       ▼                                ▼
┌─────────────────────────────────────────────────┐
│              EVIDENCE LAYER                     │
│  ledger.sh (ADR-0011) + provenance + signatures │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│                 TERRITORY                       │
│  src/ · state/ · manifests/ · forge/ · scan/    │
└─────────────────────────────────────────────────┘
```

## Ключевые компоненты

### 1. Orchestrator
Минимальный state-machine (в духе LangGraph, но без тяжёлой зависимости):
- Load task
- Match subject contract
- Create run context (budget, checkpoint, tools)
- Execute under sandbox
- Demand evidence
- Commit or reject

### 2. Subject Runtime
- Загружает `.claude/agents/*.md` + параллельный машиночитаемый контракт (`schemas/subject-contract.schema.json`)
- Проверяет scope против файловой системы
- Ограничивает tools
- Пишет промежуточные evidence
- Останавливается по budget или loop-detection (state hash)

### 3. Verifier (иммунитет)
Независимый субъект (или детерминированный checker), который:
- не видит reasoning исполнителя,
- видит только proposed effect + evidence,
- выдаёт ACCEPT / REJECT / ESCALATE.

### 4. Evidence Layer
Append-only, hash-chained — в НОУС уже реализован `src/lib/ledger.sh` (ADR-0011).
Каждая запись:
- run_id
- subject_id
- claim / action
- supporting_artifacts
- signature / hash
- timestamp

### 5. State & Self-perception
`scripts/status.sh` или `nous status` показывает:
- open tasks
- last runs + их статусы
- drift (карта vs территория)
- budget spent
- health forge/scan

## Паттерны оркестрации (из практик 2026)

- Hierarchical: Orchestrator → Specialist subjects
- Verification subagent (всегда)
- Sequential для критичных цепочек
- Parallel только внутри одного scope и с join-by-key
- HITL на destructive / public / budget-exceeded

## Почему не «просто LangGraph / CrewAI»

Они дают оркестрацию.
SINGULARIS даёт **онтологию + enforceable contracts + evidence-before-effect + конституцию репозитория**.
Фреймворк можно использовать внутри runtime, но он не является ядром.
