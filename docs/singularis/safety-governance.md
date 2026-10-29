# Безопасность и Governance SINGULARIS

## Принципы (синтез 2026)

1. **Bounded autonomy** — каждый субъект имеет явный action space.
2. **Evidence-before-effect** — нет durable evidence → нет side-effect.
3. **Independent verification** — verifier не зависит от reasoning исполнителя.
4. **Hard budgets** — токены / $ / шаги / время. Kill-switch.
5. **Loop detection** — semantic/state hashing, не «спроси агента».
6. **Human accountability** — high-stakes действия требуют человека.
7. **Oversight на эволюцию** — изменение scaffold только через ADR + тикет.

Принципы наследуют safe-defaults НОУС (`manifests/safe-defaults.yaml`): стирание дисков,
автопубликация, публичность репо выключены по умолчанию — это L4 и ниже.

## Уровни автономии

| Уровень | Что разрешено                          | Gate                  |
|---------|----------------------------------------|-----------------------|
| L0      | Чтение + анализ                        | нет                   |
| L1      | Изменение внутри scope + tests         | verifier              |
| L2      | Создание новых файлов / PR             | verifier + budget     |
| L3      | Изменение контрактов / axioms          | ADR + Human           |
| L4      | Destructive / public / forge wipe      | Explicit Human + 2FA  |

## Threat model (кратко)

- Prompt injection → scope + tool allowlist + sandbox
- Infinite loops → state hash + max_steps
- Budget exhaustion → hard ceiling на orchestrator
- Hallucinated claims → evidence must be reproducible
- Scaffold drift → все изменения scaffold через тикеты
- Supply-chain → pins по SHA (уже в НОУС, ADR-0004/0010)

Полный контекст находок и доктрина реагирования — ADR-0012 (доктрина секретов)
и аудит `docs/genesis/audit-2026-10-29.md`.

## Audit

Каждый run оставляет:
- полный evidence trail
- hash состояния до/после
- список вызванных tools
- decision verifier'а

Это позволяет offline-replay и forensic analysis.
