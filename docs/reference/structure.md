# Референс: структура репо

Каноническая карта тела. Тест `tests/test_structure.py` следит за существованием
ключевых путей; этот документ — человеческое зеркало той же карты.

## Корень

| Путь | Орган |
|---|---|
| `README.md` | витрина и точка входа |
| `AGENTS.md` | конституция агентов (≤8KB, плотный индекс) |
| `LICENSE` | MIT |
| `CONTRIBUTING.md` | вход субъекта |
| `SECURITY.md` | политика безопасности и приватное репортование |
| `AI_POLICY.md` | правила ИИ-вкладов |
| `CHANGELOG.md` | журнал изменений (release-please) |
| `Makefile` | единый интерфейс команд |
| `mkdocs.yml` | конфиг документации (Диатаксис-навигация) |
| `.mise.toml`, `.envrc.example`, `.editorconfig`, `.gitattributes`, `.gitignore` | гигиена среды |
| `.pre-commit-config.yaml`, `requirements-dev.txt` | локальный контур проверок |

## Каталоги

| Каталог | Содержание |
|---|---|
| `.claude/agents/` | контракты субъектов (5 ролей, формат YAML-фронтматтер) |
| `.claude/settings.json` | deny-правила для Claude Code |
| `.cursor/rules/` | `nous-core.mdc` (всегда), `forge-safety.mdc` (глоббы форжа) |
| `.devcontainer/` | воспроизводимая среда |
| `.github/workflows/` | `ci.yml`, `release.yml` |
| `.github/ISSUE_TEMPLATE/` | тикет субъекта, дефект, конфиг |
| `docs/getting-started/` | учебник |
| `docs/guides/` | руководства: субъект, ветка исполнения, релиз |
| `docs/concepts/` | аксиомы, карта=территория, субъекты, контур, дефолты |
| `docs/spec/` | ТЗ, roadmap, реализация 01–07 |
| `docs/decisions/` | ADR (MADR, непрерывная нумерация) |
| `docs/reference/` | этот референс, команды, security baseline |
| `src/forge/` | целевой код форжа (появляется по тикетам R2–R4) |
| `tests/` | исполняемая карта: test_structure, test_workflows, test_docs |
| `scripts/` | bootstrap, verify, state, gen_llms, pin_action |
| `manifests/` | pins.yaml, safe-defaults.yaml |
| `state/` | снимки состояния |
| `tasks/` | open/, done/ — очередь воли |
| `templates/` | самокопирование (R6) |

## Субъекты (реестр ролей)

| Роль | Зона | Ключевой запрет |
|---|---|---|
| `forge-architect` | спеки, ADR, `docs/spec/**`, `src/forge/**` | не исполняет деструктив, не пушит в main |
| `forge-builder-win` | `src/forge/win/**` | операции над носителями хоста |
| `forge-builder-linux` | `src/forge/linux/**` | запись на физические носители |
| `forge-verifier` | верификация | не чинит сам, не ослабляет тесты |
| `forge-librarian` | ADR-формат, CHANGELOG, state | не меняет смысл решений |

## Инвариант

Любое новое место в репо появляется одновременно в трёх картах: здесь,
в `mkdocs.yml` (nav) и в тесте структуры. Три карты расходятся — красный CI.
