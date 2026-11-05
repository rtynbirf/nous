# Тикет 0009 — singulyar: вынос публичной константы Innertube из HEAD + резолв алерта

Роль: forge-verifier · Создан: 2026-10-29 · Исполнен: 2026-10-29 (той же сессией,
оператор с мандатом владельца) · Статус: ЗАКРЫТ, доказательства ниже
Источник: директива владельца («ТЫ НА СВОЁ ЗАМЕНИ»), разбор
docs/genesis/sintez-public-repo-synthesis.md §5, доктрина ADR-0012 (класс B).

## Цель (исходная)

Закрыть secret-scanning алерт #1 публичного репо `rtynbirf/singulyar` своим путём
(класс B доктрины ADR-0012), не ломая юзерскрипт, без похода в чужую Google Cloud
Console.

## Критерии приёмки — все выполнены

- [x] Литерал отсутствует в HEAD singulyar: `grep -c AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8` → 0
- [x] Синтаксис проверен: `node --check ИНСТРУМЕНТЫ/RUVSON_Grabber.user.js` → OK (node v24.22.1)
- [x] Алерт #1 резолвнут через API: state=resolved, resolution=false_positive,
      resolved_at=2026-10-29T13:12:09Z (PATCH /secret-scanning/alerts/1)
- [x] Решение зафиксировано: ADR-0012, синтез-док §5, CHANGELOG 0.4.0 (Security)

## Доказательства (журнал)

| Факт | Метод | Результат |
|---|---|---|
| Литерал удалён из HEAD | git grep по дереву | 0 вхождений |
| Скрипт не сломан | node --check | OK |
| Поведение на youtube.com сохранено | чтение кода: key только из ytcfg; отказ честный | подтверждено |
| Публичность константы | curl+grep watch-страницы YT | 1 вхождение в ytcfg |
| Массовость константы | GitHub code search | 894 файла |
| Коммит-ревизия | push singulyar:rumu | 8fc46f9..c1989b2 |
| Резолв алерта | PATCH API | resolved/false_positive |

Примечание: комментарий к алерту через API недоступен (404 — у secret-scanning
алертов нет публичного comment-эндпоинта); доказательства живут в сообщении
коммита c1989b2 и в доках НОУСа.

## Границы соблюдены

- История git singulyar не переписана (класс B).
- Изменён только `ИНСТРУМЕНТЫ/RUVSON_Grabber.user.js` (1 файл, +8/-2).
