# AGENTS.md — конституция НОУС

Ты — субъект-агент, работающий в этом репо. Читай целиком перед первым действием.
Файл плотный по замыслу: каждая строка стоит внимания на каждой задаче.

## 1. Идентичность и рамка

- Репо = организм. Твоя задача = тикет из `tasks/open/`. Нет тикета — нет работы: предложи
  новый тикет через `tasks/README.md` и жди подтверждения владельца.
- `main` — конституция. Исполнение — **только** в ветке `agents/execution`
  (см. `docs/guides/execution-branch.md`). Изменения `main` — только через PR с верификацией.
- Ты — субъект, не индивид: твои права и границы заданы контрактом в `.claude/agents/<роль>.md`.
  Контракт сильнее твоих предпочтений.

## 2. Карта репы

```
AGENTS.md            ← ты здесь: конституция
.claude/agents/      ← контракты субъектов (роль/права/граница/протокол отчёта)
docs/                ← Diátaxis: getting-started / guides / concepts / reference
docs/decisions/      ← ADR: каждое архитектурное решение + «ПОЧЕМУ ТОЛЬКО ТАК»
docs/genesis/        ← ревизия-0: аудит, дифф с Вердиктом-1, вердикт гейта
docs/spec/           ← ТЗ форжа, дорожная карта (roadmap), пакет реализации 01–07
docs/singularis/     ← онтология 2.0 (SINGULARIS, ADR-0013): манифест/аксиомы/контур
schemas/             ← машиночитаемые контракты, evidence, тикеты (SINGULARIS)
src/forge/           ← ТЕРРИТОРИЯ (v0.2.0): probe · win · linux + единая точка входа
src/lib/             ← общий каркас (common.sh) и верификатор артефакта (verify-iso.sh)
src/runtime/         ← контур исполнения субъектов: harness MVA-H (ADR-0014, тикет 0017)
tests/               ← исполняемая карта: структура, workflows, связи, гейты форжа
scripts/             ← bootstrap.sh / verify.sh / state.sh / gen_llms.sh / pin_action.sh
manifests/           ← pins.yaml (единственный lockfile, ADR-0010) и safe-defaults.yaml
tasks/               ← open/ done/ — очередь воли (поглощается: done+open непрерывны)
state/               ← снимки состояния (эмерджентный слой; пишет scripts/state.sh)
templates/           ← самокопирование (R6)
.github/workflows/   ← ci.yml (верификация) · forge.yml (исполнение Linux-форжа, ADR-0009) · release.yml (отделён; OIDC; теги v*)
```

## 3. Команды (единственный интерфейс)

```bash
bash scripts/bootstrap.sh   # подготовка среды (идемпотентно)
bash scripts/verify.sh      # ВСЕ проверки: тесты + shellcheck + секреты + zizmor + mkdocs --strict
bash scripts/state.sh       # снимок состояния → state/ (md + JSON)
bash scripts/pin_action.sh <owner/repo> <tag>   # резолв SHA для пина
make bootstrap | verify | state

# Территория форжа (Linux-хост):
bash src/forge/forge.sh probe                    # обследование (только чтение)
NOUS_PW_HASH="$(openssl passwd -6)" bash src/forge/forge.sh debian12    # или ubuntu-2404
# Windows-хост: pwsh -File src/forge/forge.ps1 -Target win
```

Если `verify.sh` красный — твоя задача не завершена. Незавершённое не коммитится.

## 4. Железные правила (нарушение = утеря доверия субъекту)

1. **Карта = территория.** Не пиши непроверяемое. Утверждение — исполнимое (код/тест) или
   помечено гипотезой. Отчёт обязан содержать сырые выводы команд, не пересказ.
2. **Пины — только через `manifests/pins.yaml`.** Новая внешняя зависимость: сначала пин
   (`scripts/pin_action.sh`), потом использование. Actions — только по полному 40-символьному SHA,
   и SHA обязан совпадать с пином (тест-гейт ADR-0010). Выдуманные хеши запрещены: null → TOFU.
3. **Опасные дефолты пассивны.** Запрещено: стирание дисков/разделов, `rm -rf` вне рабочей
   копии, push в чужие репы, создание публичных реп, изменение workflows в ветке исполнения
   без ADR. Полный список — `manifests/safe-defaults.yaml`.
4. **Секреты запрещены.** Токены/ключи не попадают в файлы, логи, тикеты. Нашёл секрет в коде —
   тикет `security` высшего приоритета, не трогай руками.
5. **Conventional Commits.** `feat|fix|docs|test|chore|refactor|ci|build: суть`. Скоуп — орган:
   `feat(forge-win): …`, `docs(adr): …`.
6. **Решение изменено — ADR обновлён.** Новое «ПОЧЕМУ ТОЛЬКО ТАК» → `docs/decisions/NNNN-*.md`
   (MADR-подобный формат, нумерация непрерывна — тест `tests/` следит).
7. **Отчёт по тикету** = ссылка на коммит + сырые выводы verify + изменённые файлы + что НЕ
   проверено. Без доказательств тикет не переносится в `done/`.

## 5. Порядок работы над тикетом

1. Прочитай тикет `tasks/open/NNNN-*.md` → роль-исполнитель указана там.
2. `git checkout agents/execution && git pull` → ветка задачи `agents/<роль>/NNNN-<slug>`.
3. Исполняй в границах контракта. Каждое нетривиальное решение — строка в описании PR
   с «ПОЧЕМУ ТОЛЬКО ТАК / ПО ДРУГОМУ НЕТ».
4. `bash scripts/verify.sh` — зелёный обязателен.
5. PR в `agents/execution` → отчёт по п.4.7. После ревью верификатора тикет → `tasks/done/`.

## 6. Знание по требованию

- Как добавить субъекта: `docs/guides/new-subject.md`
- Как устроен контур эмерджентности: `docs/concepts/emergence.md`
- ТЗ форжа (цель всего): `docs/spec/tz-nous-forge.md`
- Дорожная карта и текущая фаза: `docs/spec/roadmap.md`
- Онтология 2.0 (SINGULARIS): `docs/singularis/index.md`
- Генеалогия (аудит/дифф): `docs/genesis/revision-0.md`
- Полный референс структуры: `docs/reference/structure.md`
