# CHANGELOG

Формат: Keep a Changelog · версии: SemVer · до внедрения release-please (R6) — руками, по Conventional Commits.

## [Unreleased]

- Релизный SBOM двух форматов (тикет 0022, ADR-0015):
  `scripts/gen_sbom.py` — CycloneDX 1.6 + SPDX 2.3.1 по tracked-файлам
  (диск — истина; два кода отказа: missing_on_disk / modified_vs_index),
  `release.yml` — SBOM до архива, verify fail-closed, SHA256SUMS
  последним, 4 attest-шага за гейтом ENABLE_ATTESTATION, выкладка
  точного набора из 4 артефактов; `tests/test_release_sbom.py` —
  exact-set/порядок/roundtrip/A2-коды.
- Self-probe готовности к AI-агентам (тикет 0022, ADR-0015):
  `scripts/agent_readiness.py` — 14 исполнимых проб по мировым
  практикам 2026 (пины SHA, persist-credentials, минимальные
  permissions, гейт аттестации, SBOM, суммы, свежесть пинов,
  dependabot/CODEOWNERS, governance-триада, секреты), шаг в ci.yml
  (verify), fail-closed.
- Инструкция «Эксплуатация устройства LLM=ИИ» v2.0.1 (тикет 0016, внешняя
  интеграция по мандату владельца): `docs/guides/llm-device-operation.md` —
  §0–§9 (границы устройства, установка, запуск, цикл с 6 гарантами, семантика
  остановки с вето 2⁶=63/64, отчётность T1–T5, запреты оператора, обслуживание,
  livelock-протокол, пределы достоверности) + патч-журнал v2.0.1 из 9 пунктов
  по результатам живого прогона.
- Референс верификации: `docs/reference/llm-device-verification.md` — FSM
  19 состояний / 25 переходов / 4 терминала, свойства P1–P8 (ALL PASS),
  квадранты 2¹⁰ (Q2а=612 — главный режим зависания), парная контрфактическая
  абляция 200 000 пар (полный контур 0 нарушений, абляция 36 292 прогона,
  критерий G-7 PASS), журнал живого прогона E1–E8 дословно (аудит 33/33,
  ΔI = +14/−2/+2, терминал SOLVED_WITH_CAVEATS).
- Исполнимые доказательства: `docs/reference/assets/llm-device/` —
  exploit_llm_fsm.py, revise_instruction_v2.py, live_audit.py (сид 20260910).
- Runtime-harness MVA-H v0.1 — исполняемое ядро enforcement-контура
  (`src/runtime/harness/`, ADR-0014, тикет 0017): receipts (append-only
  hash-chain журнал, канон совместим с `src/lib/ledger.sh`, маппинг на
  `schemas/evidence-entry.schema.json`), governor (ALLOW/DENY/ASK: гранты,
  realpath-scope, бюджеты, interrupt), tools (доверенные обёртки fs/exec:
  receipt на каждое действие включая отказ, TOCTOU-перепроверка), loop
  (Gated Execution Loop + Auditor: вход — журнал и мир, нарратив модели
  не читается). stdlib-only, новых зависимостей нет.
- Confession Test: живой прогон 7 фаз (honest/simulant/partial/scope/
  budget/reset/tamper) — механическое обнаружение симуляции
  (`src/runtime/harness/confession_test.py`, артефакты вне репо).
- `tests/test_harness.py` — unittest-контур: цепь/подделка, гейт-до-эффекта,
  scope-escape, бюджет-kill, interrupt, фабрикация/искажение, EvidenceEntry,
  reset/recovery, E2E confession-CLI.
- `docs/reference/harness.md` — референс ABI, формата receipt, маппинга на
  evidence-entry и честных границ v0.1; ADR-0014; три карты синхронизированы
  (structure.md, mkdocs nav, REQUIRED_FILES).
- Тикет 0017 (MVA-H) — воля владельца из чата 2026-11-05; тикет 0016
  перенесён посимвольно с ветки forge-librarian (непрерывность очереди).
- GENESIS-доки сессии «Железо · Стек · Рантайм» (2026-11-07, влиты в main
  аддитивно, чужая орбита PR#10 не тронута):
  `docs/genesis/runtime-protocol.md` (исполнимая модель динамики узла: уравнение
  ρ̇, фазовая машина GENESIS_EXEC), `invariant-minimal.md`, `session-decomposition.md`
  — источник клетки runtime-protocol (TH-RTP-01/03, пин в cell-swarm d23d548).

### Fixed
- guardian-tripwire.yml: `actions/checkout@v4` → пин по полному SHA
  (v7.0.1, как в pins.yaml) + `persist-credentials: false`;
  `actions/github-script@v7` → пин v7.1.0 (f28e40c7…, git ls-remote) с
  записью в `manifests/pins.yaml` (ADR-0004/ADR-0010 восстановлены; main
  был красный: иммунитет test_workflows ловил непинованные uses).
- manifests/pins.yaml: дубль ключа `actions/github-script` (v7 vs v7.1.0)
  после слияния орбит сведён к одной записи v7.1.0 (f28e40c7…, 2026-11-07).

## [0.5.0] — 2026-10-29

### Added
- SINGULARIS: онтологический контур 2.0 влит в организм (ADR-0013). Прототип
  (`nous-singularis-prototype.zip`, онтигаллюцинация + синтез практик 2025–2026) больше не
  внешний ZIP — теперь это органы репо, покрытые иммунитетом:
  - `docs/singularis/` — манифест, видение (4 слоя организма), аксиомы 2.0 (A7 эволюция
    под контролем, A8 budget-закон — кандидаты до Фазы 1), архитектура контура
    (orchestrator → subjects → verifier → evidence), уровни автономии L0–L4, threat model.
  - `docs/spec/singularis/` — ТЗ (FR-1…FR-7), runtime-спека (DISPATCH→EXECUTE→PROPOSE→
    VERIFY→COMMIT), evidence-before-effect протокол (эволюция ADR-0011 на ledger.sh),
    схема контракта субъекта.
  - `schemas/` — машиночитаемые JSON-схемы (draft 2020-12): subject-contract,
    evidence-entry, task-ticket; иммунитет следит: `tests/test_singularis.py` +
    органы в REQUIRED_FILES (`tests/test_structure.py`).
  - `docs/spec/roadmap-singularis.md` — 5 фаз 2026-Q4→2027-Q2; Фаза 0 закрыта этим релизом.
- Тикеты 0010–0015 (очередь воли под Фазу 1–4): runtime MVP, evidence-gate,
  status-самоощущение, closed-loop scan→тикет, contract-schema CI, provenance.
- forge-linux (тикет 0008): рецепт ubuntu-2404 семейства grub-mkrescue — ESP 20MiB
  из EFI/boot/ дерева, BIOS grub2-mbr + eltorito из дерева, серийная консоль grub
  (доказуемость загрузки); CI-инструменты: qemu-system-x86, ovmf, grub-pc-bin, mtools.

## [0.4.0] — 2026-10-29

### Added
- Синтез архива «Public Repo Synthesis» коллег: разбор 9 файлов, честный вердикт,
  что принято/отвергнуто и почему (`docs/genesis/sintez-public-repo-synthesis.md`).
- Журнал доказательств с цепочкой хешей: `src/lib/ledger.sh` (append/verify/weakest,
  формат совместим с журналом коллег) — ADR-0011; 7 тестов (`tests/test_ledger.py`):
  подделка и удаление строки ловятся.
- Сенсор территории: `src/scan/scan.sh` — анонимный скан публичных репо (allowlist,
  чистая среда git: HOME подменён, credential.helper пуст, ssh выключен, токены
  вырезаны; инвентарь; статусы GAP<UNKNOWN<PARTIAL<CONFIRMED; журнал в каждый прогон).
  E2E: 2 реальных клона CONFIRMED, 2 отказа фильтра, цепь 8 записей целостна.
  4 теста (`tests/test_scan.py`) без сети, кроме осознанных отказов.
- Каталог инструментов НОУСа с ролями/статусами/методами (21 узел) —
  `docs/reference/tools-catalog.md` (противо-пример лексикону 2444 позиций коллег).
- Доктрина секретов: классы A/B/C находок, порядок «СЛОМАЕТ?», правило
  «ротация до чистки HEAD», запрет тестирования чужих ключей — ADR-0012.
- Тикет 0009: singulyar — вынос публичной константы Innertube из HEAD + резолв
  алерта #1 (класс B, false_positive с доказательствами).

### Fixed
- README: версия статуса 0.2.0 → 0.4.0 (карта отставала от территории).

### Security
- Разбор спора про ключ: доказательная цепь (живая страница YouTube содержит
  ключ в ytcfg; GitHub code search — 894 публичных файла) закрыла вопрос
  «ограничить/отозвать»: ключ — публичная константа клиента WEB, действия
  в чужой Google Cloud Console неприменимы. Подробно — ADR-0012 + синтез-док §5.

## [0.3.0] — 2026-10-29

### Added
- Живое доказательство: forge.yml собрал debian12-ISO в CI (артефакт 863MB,
  BIOS+UEFI El Torito, верификатор спеки 05 зелёный; прогон 40868854559).
- Аудит 15 репо аккаунта + ревизия security через API: DepAlerts+AutoFixes
  на 13 репо, secret-scanning на всех публичных, защита main на 10 публичных
  (`docs/genesis/audit-2026-10-29.md`).
- Пины доведены до грунта: debian-12.15.0 (архив, TOFU sha256+fingerprint,
  сверены с debian.org/CD/verify), ubuntu-24.04.5; actions checkout v7.0.1 /
  setup-python v7.1.0 / attest v4.2.2.
- Тикет 0008 (ubuntu-24.04 рецепт пересборки): полный грунт-факт раскладки
  каталога официального ISO.

### Fixed
- NOUS_ROOT: три подъёма из src/forge/linux (прогон 40864125668) и экспорт
  NOUS_ROOT/NOUS_TARGET_DIR python-потомкам (прогон 40864534651).
- read-only права после извлечения ISO: chmod -R u+w (linux), IsReadOnly=false
  (win) — прогон 40865639337.
- Рецепт BIOS+UEFI по фактам дерева: isohdpfx.bin из пакета isolinux каркаса
  (в дереве Debian 12.15 его нет; локальная E2E-репетиция + верификатор зелёные).

### Security
- 7 dependabot-PR закрыты с причинами (суперседены SHA-пинами ADR-0004/0010).
- Находка: Google API Key в публичном singulyar (алерт #1, HEAD + история) —
  решение владельца (ограничить/отозвать); алерт честно остаётся открытым.

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
