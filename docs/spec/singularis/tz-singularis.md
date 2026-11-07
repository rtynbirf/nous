# ТЕХНИЧЕСКОЕ ЗАДАНИЕ
## SINGULARIS — Эмерджентный Сингулярный Универсальный Прототип

**Версия ТЗ:** 0.1.0
**Дата:** 2026-10-29
**Заказчик:** развитие НОУС
**Исполнитель:** субъекты + человек

---

## 1. Цель

Создать минимальный, самодостаточный, доказуемый контур, который превращает репозиторий НОУС (и любой другой) в живой организм субъектов с enforceable контрактами, evidence-before-effect и контролируемой эволюцией scaffold.

## 2. Объект автоматизации

- Загрузка и валидация контрактов субъектов
- Назначение и исполнение тикетов из `tasks/open/`
- Gated execution (sandbox + budget + scope)
- Независимая верификация
- Запись durable evidence
- Self-perception (`status`)
- Controlled scaffold evolution

## 3. Функциональные требования

### FR-1. Subject Contract Loader
- Читает `.claude/agents/*.md` + машиночитаемый контракт, валидирует по `schemas/subject-contract.schema.json`
- Обязательные поля: id, version, role, scope, tools, budget, report_protocol, verifier
- Отказывает в загрузке при нарушении схемы

### FR-2. Task Dispatcher
- Сканирует `tasks/open/`
- Матчит тикет с подходящим субъектом (по tags / role)
- Создаёт run context

### FR-3. Runtime Executor
- Запускает субъект в ограниченной среде
- Применяет scope (path allow/deny)
- Считает шаги / токены / $
- При превышении budget — kill + evidence
- Детектирует loops через hash состояния

### FR-4. Evidence Gate
- Перед любым side-effect (write, commit, PR, forge) требует durable evidence entry
- Evidence должна содержать: claim, supporting artifacts, subject_id, run_id, hash

### FR-5. Independent Verifier
- Получает proposed effect + evidence
- Не получает chain-of-thought исполнителя
- Возвращает ACCEPT / REJECT / ESCALATE_TO_HUMAN

### FR-6. Status & Self-perception
- Команда `nous status` / `scripts/status.sh` показывает:
  - open / in-progress / done тикеты
  - последние runs и их outcomes
  - drift indicators
  - budget spent за период
  - health ключевых органов (forge, scan, tests)

### FR-7. Scaffold Evolution Gate
- Изменение контрактов, axioms, verifier-правил, budgets — только через специальный тикет типа `scaffold-evolution`
- Требует ADR + Human approval (L3)

## 4. Нефункциональные требования

- **Самодостаточность:** после bootstrap всё работает offline (кроме LLM API, если выбран)
- **Воспроизводимость:** любой evidence entry должен позволять replay
- **Читаемость:** человек может понять любой run по evidence без LLM
- **Минимализм:** ядро runtime < 1500 LOC Python/Bash (без учёта LLM-клиентов)
- **Совместимость:** может использовать LangGraph/CrewAI внутри, но не зависит от них

## 5. Критерии приёмки (MVP)

1. `bash scripts/bootstrap.sh` поднимает среду
2. Существует хотя бы один валидный машиночитаемый контракт субъекта
3. Можно положить тикет в `tasks/open/` и запустить `nous run`
4. Субъект выполняет задачу в scope, пишет evidence, verifier принимает/отклоняет
5. `nous status` показывает живое состояние
6. Попытка выйти за scope или budget фиксируется в evidence и блокируется
7. Все пины и тесты зелёные

## 6. Вне скоупа MVP

- Полноценный multi-agent debate
- Автоматический RSI модели
- GUI dashboard (достаточно CLI + markdown)
- Windows-native runtime (достаточно WSL / remote)

## 7. Метрики успеха

- Time-to-first-verified-run < 15 минут после clone
- 100% side-effects имеют evidence
- 0 неконтролируемых выходов за scope в тестовых прогонах
- Возможность offline-audit любого run
