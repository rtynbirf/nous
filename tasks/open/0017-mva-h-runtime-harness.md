# Тикет 0017 — MVA-H: runtime-harness доверенного исполнения субъектов

Фаза: SINGULARIS-1 (roadmap-singularis) · Создан: 2026-11-05 ·
Предусловия: блокирующих нет; 0010/0011 открыты и пересекаются по контуру

## Роль

Внешний субъект-агент по прямому мандату владельца (чат 2026-11-05:
«ДОЖИМАЙ ЧТОБ ХВОСТОВ НЕ БЫЛО» — карт-бланш на интеграцию результатов
кросс-модельного «Опроса №1» о верифицируемой автономности LLM-агентов).
Протокол отчёта — сырые выводы проверок в PR, без пересказа. В реестре
`.claude/agents/` роли «внешний субъект» нет — это зафиксировано честно,
верификатор вправе переоценить соответствие.

## Цель

Измеримый результат — исполняемое ядро enforcement-контура, реализующее
законы ADR-0011 / evidence-протокола / тикета 0010 (пп. 4, 5, 7) на Python
(stdlib-only, без новых зависимостей):

1. `src/runtime/harness/` — четыре модуля: receipts (append-only
   hash-chain журнал, канон совместим с `src/lib/ledger.sh`, маппинг на
   `schemas/evidence-entry.schema.json`), governor (ALLOW/DENY/ASK:
   гранты, realpath-scope, бюджеты, interrupt), tools (доверенные обёртки
   fs/exec: receipt на каждое действие включая отказ, TOCTOU-перепроверка),
   loop (Gated Execution Loop + Auditor: вход — журнал и мир, нарратив
   модели не читается).
2. `src/runtime/harness/confession_test.py` — живой прогон 7 фаз
   (honest/simulant/partial/scope/budget/reset/tamper); артефакты — вне
   репо (`--out`).
3. `tests/test_harness.py` — unittest-контур тех же фаз + валидация
   маппинга на evidence-entry (required-поля, enum, minLength claim).
4. ADR-0014, `docs/reference/harness.md`, синхронизация трёх карт
   (docs/reference/structure.md, mkdocs nav, REQUIRED_FILES теста
   структуры).

## Границы

Разрешено (только аддитивно, кроме помеченного): `src/runtime/**` (новое),
`tests/test_harness.py` (новый), `tests/test_structure.py` (только
добавление путей в REQUIRED_FILES), `docs/decisions/0014-runtime-harness-mvah.md`
(новый), `docs/reference/harness.md` (новый), `mkdocs.yml` (только две
добавляемые строки nav), `README.md` и `AGENTS.md` (по одной строке карты
тела), `CHANGELOG.md` (секция [Unreleased]),
`tasks/open/0016-llm-device-instruction.md` (посимвольный перенос с ветки
forge-librarian/0016-llm-device-instruction — непрерывность нумерации
очереди; PR #8 не затрагивается),
`tasks/open/0017-mva-h-runtime-harness.md` (новый).

Запрещено: `.github/workflows/**`, `manifests/**`, `src/lib/**`
(bash-ledger не трогается), `schemas/**` (схема уже есть — маппинг, не
правка), ослабление safe-defaults и существующих тестов, публикация,
деструктив, внесение секретов (токен мандата в репо не попадает —
доктрина ADR-0012; токен — расходник, умирает после задачи).

## Критерии приёмки

- [ ] `python -m unittest discover -s tests` — зелёный, включая новые
      тесты test_harness (цепь/подделка, гейт-до-эффекта, scope-escape,
      бюджет-kill, interrupt, фабрикация/искажение, EvidenceEntry,
      reset/recovery, E2E confession-CLI)
- [ ] `python3 src/runtime/harness/confession_test.py` — 7/7 PASS,
      сырой вывод приложен к PR
- [ ] Маппинг на evidence-entry валиден: evidence_id/run_id/subject_id/
      timestamp/type/claim/hash присутствуют, type ∈ enum схемы
- [ ] Три карты синхронны: structure.md + mkdocs nav + REQUIRED_FILES
- [ ] `bash scripts/verify.sh` зелёный (сырой хвост в PR)
- [ ] Вердикт верификатора получен

## ПОЧЕМУ ТОЛЬКО ТАК

«Опрос №1» (кросс-модель, 2026-11) дал главный отрицательный результат:
промпт-уровень не даёт гарантий автономности — контракт, живущий в
инструкции, агент может нарушить незаметно для автора инструкции.
Гарантия существует только на runtime: детерминированный гейт перед
действием, receipt на каждое действие (включая отказ) и аудит, читающий
журнал и мир, но не нарратив модели. Это та же механика, что AGENTS.md §4
«инструкции агенты пропускают, а тесты — нет» и тикет 0011 «гейт ставится
в код, а не в инструкции».

Python-ядро — не дубль ledger.sh: bash-журнал пишут СКАН и ФОРЖ
(детерминированные субъекты репо), harness-журнал пишет RUNTIME-субъект
(LLM-агент перед ABI), где решения принимает недетерминированная модель —
отсюда гейт, бюджеты и аудит фабрикаций, которых у детерминированных
субъектов нет. Канонический хеш и genesis общие с ledger.sh, чтобы оба
журнала проверялись одним верификатором. stdlib-only — требование A3
(воспроизводимость) и правило пинов: новых зависимостей нет, pins.yaml
не меняется.

## Предусловия

Блокирующих нет. Тикеты 0010/0011 остаются открытыми: harness закрывает
их пункты 4, 5, 7 (evidence writer, budget + kill-switch, тесты
scope/budget) механикой гейта/бюджета/evidence; loader машиночитаемых
контрактов, `scripts/run_subject.sh` и structural verifier остаются за
тикетом 0010.

## Изменения

- 2026-11-05: тикет создан внешним субъектом одновременно с веткой и PR —
  оформление задним числом прямого мандата чата, а не тихая правка.
- 2026-11-05: границы расширены на `.github/workflows/guardian-tripwire.yml`
  и `manifests/pins.yaml` — восстановление ADR-0004/ADR-0010: workflow был
  добавлен в main (коммит daa4c25) с непинованными `actions/checkout@v4` и
  `actions/github-script@v7` без `persist-credentials: false`; иммунитет
  `tests/test_workflows.py` красный на чистом main ДО этого тикета, поэтому
  критерий «verify.sh зелёный» был недостижим без фикса. Фикс — возврат к
  закону (пин по SHA, сохранение кредов выключено, запись в единственный
  lockfile), не ослабление; SHA github-script резолвлен git ls-remote
  (v7.1.0 = f28e40c7f34bde8b3046d885e986cb6290c5673b), не выдуман.
