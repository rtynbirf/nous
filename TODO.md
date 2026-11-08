# TODO · nous · живой трекер

> Живой трекер-мемо Волны ×5 (2026-11-09). Полный реестр аккаунта: github-runbook → РЕЕСТР-НЕДОДЕЛАННОГО-2026-11-09.md · мастер-индекс: github-runbook#10.

## 1. Открытые issues

Нет открытых issues (снимок /tmp/scan/state.json 2026-11-09, волна ×5-B).

## 2. Честные хвосты ⬜

- ⬜ Красные в истории не перекрашиваются (append-only): ci 42514456648 (19:19, PR 46c05f0 — pins-lockfile расходился) и ПУЛЬС 42516341871 (19:42, push без кредов) были честными; оба контура зелёные с 19:29 / 19:45.
- ⬜ ПУЛЬС пишет в PULSE.md от имени pulse-bot (github-actions[bot] e-mail) — токен-подстановка в self-audit.yml обязательна (persist-credentials: false по канону; без x-access-token git push падает «could not read Username»). Секрет/токен не внешний, штатный GITHUB_TOKEN — устойчиво.
- ⬜ Живая сверка manifests/pins.yaml ↔ uses-SHA всех workflows — это test_pins_yaml_is_single_lockfile (ADR-0010): каждый новый actions-pин добавлять СНАЧАЛА в pins.yaml, потом в workflow.

## 3. Что делать следующей волне

- Локальное репро: python3 -m unittest tests.test_workflows -v (6 тестов: пин-lockfile, persist-credentials, опасные триггеры, permissions).
- При апгрейде actions/*: обновить sha в manifests/pins.yaml (verified_at = дата живой сверки), затем в workflow — тест ловит расхождение раньше CI.
- ПУЛЬС: показания коммитятся только при существенном изменении (нормализация бакета свежести против «ритм без шума» течёт) — не отключать нормализацию.
