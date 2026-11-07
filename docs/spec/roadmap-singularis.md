# Дорожная карта SINGULARIS
## 2026-Q4 → 2027-Q2

### Фаза 0 — Онтология и спецификации (закрыта 2026-10-29)
- [x] Манифест, аксиомы v2, ТЗ, архитектура, протоколы, схемы (прототип 0.1.0-proto)
- [x] Влить ключевые документы в НОУС: `docs/singularis/`, `docs/spec/singularis/`, `schemas/`
- [x] Создать тикеты под runtime: 0010–0015 (в прототипе планировались как 0006–0010 —
      номера заняты живой очередью воли, сдвиг зафиксирован в ADR-0013)
- [x] Принятие решения: ADR-0013

### Фаза 1 — Минимальный Runtime (2–4 недели)
**Цель:** один субъект может взять тикет, выполнить в scope, оставить evidence, пройти verifier.

- [ ] `src/runtime/` — loader контрактов + schema validation (тикет 0010)
- [ ] `nous run <task_id>` (или `scripts/run_subject.sh`)
- [ ] Простой structural verifier (path + test results)
- [ ] Evidence writer (JSONL + hash, поверх `src/lib/ledger.sh` — тикет 0011)
- [ ] Budget + max_steps kill-switch
- [ ] `nous status` (базовый — тикет 0012)
- [ ] Тесты на scope violation и budget exceed

**Критерий выхода:** один end-to-end run по реальному тикету из tasks/open/ с зелёным verifier.

### Фаза 2 — Orchestrator + Multi-subject (3–5 недель)
- [ ] Dispatcher: выбор субъекта по tags/role
- [ ] Parallel runs внутри одного scope (с join)
- [ ] Checkpointing run state
- [ ] Loop detection (state hash)
- [ ] Интеграция с существующим forge/scan (они становятся субъектами)

### Фаза 3 — Evidence-before-effect hardening + Governance
- [ ] Все write/commit/PR идут только через gate (тикет 0011)
- [ ] Hash-chained evidence (готово: ledger.sh — расширить на runs)
- [ ] L3 scaffold-evolution тикеты + ADR gate
- [ ] Human escalation channel (GitHub issue / file)

### Фаза 4 — Эмерджентность и самоощущение
- [ ] Богатый `nous status` + markdown dashboard в state/ (тикет 0012)
- [ ] Автоматическое порождение тикетов из scan (GAP → task — тикет 0013, closed loop)
- [ ] Controlled scaffold proposals (промпты, budgets, verifier rules)
- [ ] Provenance query: «откуда взялся этот файл?» (тикет 0015)

### Фаза 5 — Универсализация (2027)
- [ ] Template для новых репозиториев (`templates/singularis-repo`)
- [ ] Документация «как превратить любой репо в SINGULARIS»
- [ ] Опциональный LangGraph/CrewAI adapter (не ядро)
- [ ] Метрики Agentic SLO (success rate, evidence coverage, scope violations = 0)

## Принципы приоритизации

1. Сначала **enforceable** минимальный контур.
2. Потом удобство и красота.
3. Эволюция scaffold — только после того, как evidence-gate работает надёжно.
4. Никакого RSI модели до фазы 5 (и то под жёстким oversight).

## Риски и митигация

| Риск                        | Митигация                              |
|-----------------------------|----------------------------------------|
| Runtime слишком сложный     | Жёсткий LOC-лимит на ядро (<1500)      |
| LLM галлюцинирует evidence  | Verifier не доверяет тексту, только артефактам |
| Scope bypass                | OS-level sandbox + path checks         |
| Бесконечные loops           | State hash + hard step limit           |
| Потеря самодостаточности    | Всё должно работать после bootstrap    |
