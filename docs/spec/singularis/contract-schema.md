# Схема контракта субъекта

Контракт — единственный источник прав субъекта.

## Обязательные поля

```yaml
id: forge-linux
version: "1.2.0"
role: "Строитель Linux ISO-образов"
scope:
  allow:
    - "src/forge/linux/**"
    - "manifests/pins.yaml"
    - "tests/forge/**"
  deny:
    - "src/forge/win/**"
    - ".github/workflows/release.yml"
tools:
  - bash
  - read_file
  - write_file
  - run_tests
budget:
  max_steps: 30
  max_tokens: 80000
  max_cost_usd: 1.5
report_protocol: |
  1. Кратко что сделано
  2. Список изменённых путей + hashes
  3. Результаты тестов
  4. Evidence entry id
forbidden:
  - "Любые сетевые запросы кроме apt mirror из pins"
  - "Изменение axioms и контрактов других субъектов"
verifier: "default-structural"
```

Машиночитаемая схема: `schemas/subject-contract.schema.json` (draft 2020-12).
Обязательные поля схемы: id, version, role, scope, tools, budget, report_protocol.

## Машиночитаемость

- Markdown для человека (`.claude/agents/*.md`, уже существует — 5 контрактов)
- Параллельный `.contract.yaml` рядом с md для runtime
- Валидация по JSON Schema — в CI (тикеты 0010, 0014)
- Источник прав один: при расхождении md и yaml — runtime отказывает run'у
  (расхождение = баг scaffold, чинится тикетом, не «догадками» исполнителя)
