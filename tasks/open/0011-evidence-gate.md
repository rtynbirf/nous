# Тикет 0011 — SINGULARIS: evidence-gate для side-effects

Фаза: SINGULARIS-1/3 (roadmap-singularis) · Создан: 2026-10-29 · Предусловия: 0010

## Роль

forge-architect (гейт-механика) + forge-verifier (критерии); исполняет субъект с правом
изменения src/lib и точек входа.

## Цель

FR-4 ТЗ (`docs/spec/singularis/tz-singularis.md`): ни один side-effect (write вне рабочей
копии, commit, push, PR, forge-сборка) не проходит без durable evidence-записи
(`schemas/evidence-entry.schema.json`), писаемой ДО эффекта в журнал `src/lib/ledger.sh`:

1. Обёртка-гейт для forge.sh / scan.sh / run_subject.sh: attempt → evidence → effect;
   отказ без evidence — ошибка, а не предупреждение.
2. Verifier decision (ACCEPT/REJECT/ESCALATE) пишется в тот же журнал.
3. Replay-тест: по журналу восстанавливается, что было предложено и почему принято.

## Границы

Разрешено: `src/lib/**`, `src/forge/forge.sh`, `src/scan/scan.sh`, `src/runtime/**`,
`tests/**`, `schemas/**`, `docs/spec/singularis/**`, CHANGELOG.
Запрещено: ослабление safe-defaults, `manifests/**` без ADR, release.yml.

## Критерии приёмки

- [ ] Попытка side-effect без evidence падает с ошибкой (тест)
- [ ] Каждая запись гейта валидна по схеме evidence-entry
- [ ] Цепочка хешей журнала целая после прогона (ledger verify)
- [ ] Replay-тест зелёный; verify.sh зелёный

## ПОЧЕМУ ТОЛЬКО ТАК

Evidence-before-effect — главный закон SINGULARIS и операционализация A2: эффект без
доказательства = карта, не совпадающая с территорией. Гейт ставится в код, а не в
инструкции, потому что инструкции агенты пропускают, а тесты — нет.
