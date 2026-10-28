# Референс: команды

Все команды исполняются из корня репо. Одна задача = одна команда.

## Жизненный цикл

| Команда | Что делает | Когда |
|---|---|---|
| `bash scripts/bootstrap.sh` | проверяет git/python, ставит `requirements-dev.txt`, активирует pre-commit-хуки | после клона, идемпотентно |
| `bash scripts/verify.sh` | unittest + shellcheck + pre-commit (gitleaks) + zizmor + `mkdocs build --strict` | перед любым PR, обязан быть зелёным |
| `bash scripts/state.sh` | снимок состояния → `state/snapshot-<дата>.md` | после значимых фаз |
| `bash scripts/gen_llms.sh` | генерирует `llms.txt` из `docs/` | локально и в CI |
| `bash scripts/pin_action.sh <owner/repo> <tag>` | резолв commit-SHA для пина | при добавлении/обновлении action |
| `make bootstrap` / `make verify` / `make state` / `make release` | алиасы через Makefile | по вкусу |

## Git-поток (субъекты)

```bash
git checkout agents/execution && git pull
git checkout -b agents/<роль>/<NNNN>-<slug>   # ветка задачи от тикета
# ... исполнение ...
bash scripts/verify.sh                         # зелёный обязателен
git commit -m "feat(скоуп): суть"              # Conventional Commits
# PR → agents/execution; отчёт по протоколу тикета
```

## CI/release

- `ci.yml`: на push в `main`, `agents/**` и на PR; jobs: verify, security, docs.
- `release.yml`: на тег `v*`; архив docs-сайта + SHA256SUMS; аттестация за гейтом
  `ENABLE_ATTESTATION=1` (см. [гайд по релизу](../guides/release.md)).

## Частые вопросы

**verify.sh красный, а локально всё работает.** Карта строже окружения:
сначала `bash scripts/bootstrap.sh`, затем повтор; не прошло — тикет `[bug]`
с сырым выводом.

**Нужен новый внешний ресурс.** `pin_action.sh` (actions) или калибровка
по [спеке 01](../spec/implementation/01-sources.md) → запись в
`manifests/pins.yaml` → потом использование в коде.

**Нужна опасная операция.** Четыре гейта
[спеки 06](../spec/implementation/06-safe-defaults.md) и явное согласие
владельца. Без всех четырёх — нет.

## Инвариант

Нет ни одной команды, которая делает «два дела». Если кажется, что нужна, —
это два тикета.
