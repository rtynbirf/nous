# Copilot: инструкции

Конституция репо — `AGENTS.md` в корне; читай её первой. Кратко:

1. Работай только в ветке `agents/execution` и по тикету из `tasks/open/`.
2. Границы и права — по контракту роли в `.claude/agents/`.
3. Опасные дефолты пассивны: никакого деструктива, секретов, публикаций.
4. Внешние зависимости — пин по SHA через `scripts/pin_action.sh` → `manifests/pins.yaml`.
5. Отчёт = сырые выводы команд + зелёный `bash scripts/verify.sh`.
6. Коммиты: Conventional Commits (`feat|fix|docs|test|chore|refactor|ci|build(скоуп): суть`).

Путь-специфичное: в `src/forge/**` дополнительно действует
`docs/spec/implementation/06-safe-defaults.md` (запрет деструктивных операций дисков).
