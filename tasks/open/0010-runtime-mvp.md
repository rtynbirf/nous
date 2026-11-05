# Тикет 0010 — SINGULARIS Фаза 1: runtime субъектов MVP

Фаза: SINGULARIS-1 (roadmap-singularis) · Создан: 2026-10-29 · Предусловия: нет (спеки и схемы готовы — ADR-0013)

## Роль

forge-architect (дизайн контура) + forge-librarian (спека → код); verifier — forge-verifier.

## Цель

Минимальный исполняемый контур (ТЗ: `docs/spec/singularis/tz-singularis.md`, спека:
`docs/spec/singularis/runtime-spec.md`):

1. `src/runtime/` — loader машиночитаемых контрактов + валидация по
   `schemas/subject-contract.schema.json` (отказ загрузки при нарушении).
2. Точка входа `nous run <task_id>` (bash: `scripts/run_subject.sh`).
3. Structural verifier (path scope + результаты тестов) — независим от исполнителя.
4. Evidence writer поверх `src/lib/ledger.sh` (ADR-0011) — run-записи в общий журнал.
5. Budget + max_steps kill-switch (спека runtime-spec, раздел Budget Model).
6. Базовый `nous status` (см. тикет 0012 — можно заглушку с честным «не реализовано»).
7. Тесты: scope violation блокируется, budget exceed → kill + evidence.

## Границы

Разрешено: `src/runtime/**`, `scripts/**`, `tests/**`, `schemas/**`, `docs/spec/singularis/**`,
`.claude/agents/*.contract.yaml` (новые машиночитаемые слои), CHANGELOG.
Запрещено: `manifests/**` без ADR, `.github/workflows/release.yml`, изменение axioms (L3).

## Критерии приёмки

- [ ] Контракт валидируется схемой; нарушение схемы → отказ загрузки с внятной ошибкой
- [ ] End-to-end run по реальному тикету: evidence → verifier ACCEPT (или честный REJECT)
- [ ] Budget exceed → kill + evidence о причине (A8-кандидат enforcement)
- [ ] Scope violation (путь вне allow) → блокировка + evidence
- [ ] Ядро < 1500 LOC; `bash scripts/verify.sh` зелёный

## ПОЧЕМУ ТОЛЬКО ТАК

Без runtime контракты — мёртвые декларации (A1: поведение возникает из контура, не из
файлов). Порядок «enforceable минимальный контур → удобство» — принцип №1 дорожной карты.
Verifier отделён от исполнителя — практикa verification subagent (2026): тот, кто
предлагает эффект, не оценивает свой же эффект.
