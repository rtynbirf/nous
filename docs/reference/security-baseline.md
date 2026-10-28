# Референс: базовый уровень безопасности

Состояние защиты на 2026-10-29 (версия скелета 0.1.0). Канонические файлы:
`SECURITY.md`, `manifests/safe-defaults.yaml`, `manifests/pins.yaml`.

## Слой 1 — права и границы

| Мера | Реализация | Урок-прецедент |
|---|---|---|
| Минимальные permissions в CI | `contents: read` на уровне workflow и job | Shai-Hulud |
| Checkout без креденшелов | `persist-credentials: false` | кража GITHUB_TOKEN |
| Разделение release | отдельный workflow, теги `v*` | Shai-Hulud |
| Deny-правила агентов | `.claude/settings.json` + контракты | xz-utils (индивид без контракта) |

## Слой 2 — пиннинг зависимостей

| Мера | Реализация |
|---|---|
| Actions по полному SHA | все `uses:` в workflows; тест-гейт `tests/test_workflows.py` |
| Реестр пинов | `manifests/pins.yaml`: SHA/версия + источник + дата + метод |
| Зависимости Python | `requirements-dev.txt` (диапазоны), Renovate/Dependabot — R6 |
| Скрипты-рефлексы | резолв SHA только через `scripts/pin_action.sh` |

## Слой 3 — секреты

| Мера | Реализация |
|---|---|
| Секретов в репо нет | safe-default: `secrets_in_repo: forbidden` |
| Сканирование | gitleaks в pre-commit и CI (`security` job) |
| .envrc | в `.gitignore`; коммитится только `.envrc.example` без значений |
| Логи | маскирование до записи (спека 05) |

## Слой 4 — верификация и аудит

| Мера | Реализация |
|---|---|
| Аудит воркфлоу | zizmor в CI |
| Исполняемая карта | unittest: структура, пины, ссылки документов |
| Строгая сборка доков | `mkdocs build --strict` |
| Снимки состояния | `scripts/state.sh` → `state/` |

## Границы честности (что НЕ защищено на 0.1.0)

1. Ветки технически не защищены (rulesets) — только дисциплинарно; шаг R6.
2. `actions.lock` не внедрён (ADR-0008): owner_id не верифицируется в рантайме.
3. Зависимости Python без lock-файла (pip без hash-pinning) — R6 (uv/lock).
4. Аттестация артефактов выключена по умолчанию (приватное репо; R6).
5. Scorecard-метрики не снимаются (нужен публичный репо; R6).

Каждый пункт из списка границ — тикет в R6; ничто не скрыто «под ковром».
