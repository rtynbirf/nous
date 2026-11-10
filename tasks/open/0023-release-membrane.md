# Тикет 0023 · мембрана выпуска

- **Роль:** forge-architect (спека+код) + forge-verifier (гейты)
- **Мандат:** Хозяин, чат 2026-11-10: «ПРЕЖДЕ ЧЕМ ЕЩё МУТИТЬ — ЕЩё РАЗ В ВЭБ
  ПОИЩИ ЛУЧШИЕ МИРОВЫЕ ТРЕНДЫ ПРАКТИК… СДЕЛАЙ И НАСТРОЙ ТАК КАК НИ У КОГО НЕТ».
  Веб-разведка волна-3: slsa.dev/spec/v1.2/build-provenance,
  docs.github.com (artifact attestations), scorecard.dev — верифицируемость
  релиза должна жить в CI, а не в убеждении.
- **Статус:** исполнение; после вердикта верификатора — done.

## Цель (измеримая)

1. `scripts/release_membrane.py` (stdlib-only): `self-check`, `gate`,
   `sbom-diff`; коды отказа 2/3/4/5/6 разнесены по причинам.
2. `release.yml`: мембрана между SHA256SUMS и аттестацией; по тегу `v*`
   релиз дособирается до GitHub Release с точным набором.
3. `tests/test_release_membrane.py`: тест-крест с exact-set реестром
   ADR-0015 + дрейф-сценарии (без акка красный, с акком зелёный,
   first-run зелёный).
4. `docs/decisions/0016-release-membrane.md` + nav в mkdocs.yml.
5. Полный `verify.sh` зелёный; PR влит в main; CI (ci.yml) зелёный;
   release по диспатчу зелёный.

## Границы

- Разрешено: `scripts/release_membrane.py` (новый),
  `tests/test_release_membrane.py` (новый),
  `.github/workflows/release.yml` (только вставка шагов мембраны +
  шаг издания + permissions job), `docs/decisions/0016-*.md` (новый),
  `mkdocs.yml` (nav: 1 строка), `AGENTS.md` (карта: 1 строка),
  `CHANGELOG.md` (запись), `tasks/**` (этот тикет).
- Запрещено: менять существующие шаги release.yml (инвариант exact-set
  ADR-0015 под тестом), трогать pins.yaml (новые actions не вводятся),
  трогать safe-defaults, генезис, ПУЛЬС.

## Критерии приёмки

- [ ] `python3 -m unittest discover -s tests` — зелёный (в т.ч. новый файл).
- [ ] `release_membrane.py self-check` на живом репо после сборки — зелёный.
- [ ] Тест-крест: EXACT_SET мембраны == EXPECTED_ARTIFACTS ADR-0015.
- [ ] release.yml: 4 attest-шага не тронуты, гейт ENABLE_ATTESTATION на месте.
- [ ] mkdocs build --strict зелёный.
- [ ] Живой прогон release (workflow_dispatch) — зелёный.

## «ПОЧЕМУ ТОЛЬКО ТАК»

- Живой факт 2026-11-10: три прогона release красные — `Artifact storage
  quota has been hit` (пул забит 9 версиями GHCR-образа combain-v2).
  Корень лечится санацией пула (среда N), гейт exact-set не ослабляется:
  релиз без выложенного точного набора — не релиз.
- Релиз до сих пор ничего не сверял вокруг себя: аттестат подписывал
  набор, который никто никогда не пересчитывал после публикации (A10:
  convincing ≠ verifiable). Мембрана пересчитывает — и свежий набор, и
  изданный прошлый.
- Состав организма не должен меняться молча: дрейф SBOM без акка с
  тикетом краснит релиз. «Ничего не отменять» работает в обе стороны —
  и ничего не ДОБАВЛЯТЬ молча.
- Гейт стоит ДО аттестации: подпись не ставится под непрочитанным.
