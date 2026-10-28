# CHANGELOG

Формат: Keep a Changelog · версии: SemVer · обновляется release-please (не руками).

## [0.1.0] — 2026-10-29

### Added
- Скелет НОУС: конституция (README, AGENTS.md), аксиомы в `docs/concepts/`.
- Контракты субъектов `.claude/agents/` (архитектор, сборщики win/linux, верификатор, хронист).
- Контур верификации: `ci.yml` (verify/security/docs), `release.yml` (отделён, OIDC, пины по SHA).
- Исполняемая карта: `tests/` (структура, workflows, связи документов).
- Рефлексы: `scripts/{bootstrap,verify,state,gen_llms,pin_action}.sh` + `Makefile`.
- Калибровка: `manifests/{pins,safe-defaults}.yaml` (пины 2026-10-29, опасные дефолты пассивны).
- Документы: Диатаксис-структура `docs/`, 8 ADR, ТЗ форжа, дорожная карта, пакет реализации 01–07.
- Очередь воли: `tasks/` (тики 0001–0005 по фазам R1–R5).
- Эмерджентный слой: `state/` + `scripts/state.sh`.
- Ветка исполнения: `agents/execution` для работы субъектов.
