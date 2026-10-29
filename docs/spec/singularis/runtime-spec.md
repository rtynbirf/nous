# Спецификация Runtime субъектов

## Жизненный цикл Run

```
1. DISPATCH
   - task picked from tasks/open/
   - subject contract loaded & validated (schemas/subject-contract.schema.json)
   - run_id generated
   - budget allocated
   - checkpoint created

2. EXECUTE
   - subject receives: task + contract + tools + current state snapshot
   - может делать tool calls внутри scope
   - каждый значимый шаг → intermediate evidence (optional)
   - loop detector (state hash) активен

3. PROPOSE
   - субъект формирует proposed_effect (diff / actions / claims)
   - пишет final evidence entry

4. VERIFY
   - Verifier получает proposed_effect + evidence (без CoT)
   - decision: ACCEPT | REJECT | ESCALATE

5. COMMIT or ABORT
   - ACCEPT → применить эффект, переместить тикет в done/, обновить state/
   - REJECT → откат, evidence о причине, тикет остаётся или → failed/
   - ESCALATE → human notification, run paused

6. LEARN (optional, post-MVP)
   - scaffold update proposals (только через отдельный тикет, L3)
```

## Budget Model

```yaml
budget:
  max_steps: 40
  max_tokens: 120000
  max_cost_usd: 2.50
  max_wall_time_sec: 1800
```

При любом превышении — немедленный soft-kill + evidence.

## Scope Enforcement

- path allowlist / denylist из контракта
- tool allowlist
- network policy (по умолчанию deny, кроме явно разрешённых)
- git operations только в agents/execution branch (как в НОУС)

## Loop Detection

Каждые N шагов вычисляется semantic hash (или structural hash) текущего working state.
Если три раза подряд hash похож > 0.95 — объявляется Logic Lock → kill.
