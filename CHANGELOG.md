# CHANGELOG

Формат: Keep a Changelog · версии: SemVer · до внедрения release-please (R6) — руками, по Conventional Commits.

## [0.2.0] — 2026-10-29

### Added
- Территория форжа (закрытие разрыва «конституция без органов», см. `docs/genesis/revision-0.md`):
  - probe: обследование хоста только чтением, fixture-режим, JSON+лог (`src/forge/probe/`).
  - Linux-ветка: Debian 12 preseed / Ubuntu 24.04 autoinstall, xorriso-гибрид BIOS+UEFI (`src/forge/linux/`).
  - Windows-ветка: Fido (TOFU-пин) → autounattend (WillWipeDisk=false) → oscdimg `-bootdata` (`src/forge/win/`).
  - Общая вертикаль: каркас `src/lib/common.sh`, верификатор артефакта `src/lib/verify-iso.sh` (El Torito, injected, SHA256SUMS).
  - Единая точка входа: `src/forge/forge.sh` (Linux) и `src/forge/forge.ps1` (Windows).
- CI-исполнение Linux-форжа: `forge.yml` (ночь + ручной; ADR-0009: раннер = одноразовый хост).
- ADR-0009, ADR-0010 (pins.yaml — единственный lockfile + тест-гейт сверки CI↔пины).
- YAML-форма тикета `.github/ISSUE_TEMPLATE/task.yml` (обязательные поля принудительны).
- Гейт-документ генеалогии `docs/genesis/revision-0.md` (реконструкция Вердикта-1, аудит, полный дифф).
- state.sh: машиночитаемый JSON-снимок рядом с md.

### Changed
- `manifests/pins.yaml`: секция `forge` откалибрована (официальные каналы; SHA256 — TOFU, нулевых выдуманных хешей).
- `requirements-dev.txt`: точные пины `==` (воспроизводимость; версии подтверждены dependabot-PR).
- Тест-гейты: карта органов расширена территорией; нумерация тикетов = done∪open непрерывна.
- Тикет 0002 → done (вердикт верификатора); 0001 — частично (TOFU); открыты 0006, 0007.

### Security
- Гейт «SHA из workflows обязан быть в pins.yaml» — закрыт дрейф CI↔пины (ADR-0010).
- Пароли: только криптохеш из окружения в момент рендера; в CI рождается и умирает в раннере.

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
