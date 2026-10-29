# НОУС

> **Репо — не склад файлов, а машина, порождающая истину.**
> НОУС (греч. Νοῦς — мировой Разум): порядок, вносимый в хаос. Здесь порядок вносится контуром
> «контракт → исполнение → верификация → память».

**Статус:** приватное репо-конституция + живая территория форжа · ветка исполнения: `agents/execution` · версия: `0.5.0`
**Проверено:** 2026-10-29 · все внешние пины — в [`manifests/pins.yaml`](manifests/pins.yaml) · генеалогия гейта — [`docs/genesis/revision-0.md`](docs/genesis/revision-0.md)

---

## Что это

НОУС — эталонная архитектура репозитория, построенная на шести аксиомах (плюс кандидаты
A7/A8 из SINGULARIS) и спроектированная для совместной работы человека и N агентов-субъектов. Каждый агент — субъект с контрактом
(роль, права, границы, протокол отчёта), а не индивид с прихотью. Любое утверждение в репо
либо исполняется, либо генерируется из исполняемого, либо явно помечено как гипотеза.

## Аксиомы (кратко, полностью — [docs/concepts/axioms.md](docs/concepts/axioms.md))

1. **РЕПО = ОРГАНИЗМ** — файлы это геном, поведение возникает из контура.
2. **КАРТА = ТЕРРИТОРИЯ** — CI принуждает совпадение утверждений с реальностью.
3. **САМОДОСТАТОЧНОСТЬ** — `clone → одна команда → среда + зелёные тесты`.
4. **N=СУБЪЕКТ≠ИНДИВИД** — права агентов в конфиге, не в надежде.
5. **СИНГУЛЯРНОСТЬ** — один источник истины; у артефактов есть генеалогия.
6. **ЭМЕРДЖЕНТНОСТЬ** — поведение репо больше суммы файлов (слой `state/`).

Кандидаты 2.0 (до Фазы 1 runtime): **A7 эволюция под контролем**, **A8 budget-закон** —
[docs/singularis/axioms-v2.md](docs/singularis/axioms-v2.md).

## Quickstart

```bash
git clone https://github.com/rtynbirf/nous.git && cd nous
bash scripts/bootstrap.sh   # среда: инструменты, pre-commit hooks
bash scripts/verify.sh      # карта сверяется с территорией: тесты, lint, секреты, docs
```

### Форж (территория, v0.2.0)

```bash
bash src/forge/forge.sh probe            # обследование хоста (только чтение)
NOUS_PW_HASH="$(openssl passwd -6)" bash src/forge/forge.sh debian12
NOUS_PW_HASH="$(openssl passwd -6)" bash src/forge/forge.sh ubuntu-2404
# Windows-ветка — на Windows-хосте:
#   pwsh -File src/forge/forge.ps1 -Target win
# CI: workflow forge.yml — ночью и вручную (ADR-0009)
```

### Скан (сенсор территории, v0.4.0)

```bash
NOUS_TARGET_DIR=dist bash src/scan/scan.sh examples-scan/urls.txt   # пример: examples-scan/urls.txt
# анонимный клон в чистой среде (токены вырезаны, ssh выключен), инвентарь,
# статусы GAP<UNKNOWN<PARTIAL<CONFIRMED, журнал evidence.jsonl (ADR-0011)
```

### SINGULARIS (онтологический контур 2.0, v0.5.0)

```bash
python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('schemas/*.schema.json')];print('схемы живы')"
# онтология: docs/singularis/index.md · спеки: docs/spec/singularis/ · ADR-0013
# runtime субъектов — тикеты 0010–0015 (roadmap: docs/spec/roadmap-singularis.md)
```

## Карта тела

| Путь | Орган | Зачем |
|---|---|---|
| `AGENTS.md` | Конституция агентов | плотный индекс ≤8KB, читают все инструменты |
| `.claude/agents/*.md` | Генофонд субъектов | контракты: роль/права/граница/запреты/отчёт |
| `docs/` | Знание | Диатаксис + ADR (решения с «ПОЧЕМУ ТОЛЬКО ТАК») |
| `docs/spec/` | ТЗ + дорожная карта + пакет реализации | что и в каком порядке строят агенты |
| `src/forge/` | Территория (v0.2.0) | форж ISO: probe · win (Fido+autounattend+oscdimg) · linux (preseed/autoinstall+xorriso) · `src/lib/` (каркас+верификатор+журнал ADR-0011) |
| `src/scan/` | Сенсор (v0.4.0) | анонимный скан публичных репо: allowlist, чистая среда, статусы, журнал |
| `docs/singularis/` | Онтология 2.0 (v0.5.0) | SINGULARIS: манифест, аксиомы A7/A8, контур, L0–L4 (ADR-0013) |
| `schemas/` | Генофонд машинночитаемый | JSON-схемы: контракт субъекта, evidence-запись, тикет |
| `tests/` | Иммунитет | структура, workflows, связи документов — исполняемые |
| `scripts/` | Рефлексы | bootstrap / verify / state — по одной команде на задачу |
| `manifests/` | Калибровка | пины версий, SHA, безопасные дефолты |
| `tasks/` | Очередь воли | тикеты для субъектов: open → done |
| `state/` | Самоощущение | снимки измеренного состояния (эмерджентный слой) |
| `templates/` | Размножение | репо порождает репо (copier — R6) |
| `.github/workflows/` | Нервная система | `ci` (верификация) · `forge` (исполнение Linux-форжа, ADR-0009) · `release` (отделён, OIDC) |

## Исполнение агентами

Агенты работают **только** в ветке `agents/execution` и **только** по тикету из `tasks/open/`.
Протокол: [docs/guides/execution-branch.md](docs/guides/execution-branch.md) · контракты ролей: `.claude/agents/`.

## Безопасность по умолчанию

- Стирание дисков / автопубликация / публичность репо — **выключены по умолчанию**
  ([`manifests/safe-defaults.yaml`](manifests/safe-defaults.yaml)).
- Сторонние actions — только по полному SHA (урок tj-actions, CVE-2025-30066).
- `release` отделён от `ci` и живёт на коротком OIDC-токене (урок Shai-Hulud).
- Секреты в репо запрещены; сканирование — pre-commit gitleaks в CI.

## Лицензия

[MIT](LICENSE) — © 2026 rtynbirf
