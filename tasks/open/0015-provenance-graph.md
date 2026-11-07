# Тикет 0015 — SINGULARIS: provenance — генеалогия артефактов

Фаза: SINGULARIS-3/4 (roadmap-singularis) · Создан: 2026-10-29 · Предусловия: 0011

## Роль

forge-architect (модель provenance) + forge-builder-linux/win (запись в артефакты).

## Цель

A5 операционально: у каждого значимого артефакта — полная генеалогия без ручной сборки:

1. `src/lib/provenance.sh` (bash, как ledger): формирует запись «артефакт → commit SHA +
   пин(ы) из manifests/pins.yaml + run_id + subject_id + journal-хеш + timestamp».
2. Запись пишется рядом с артефактом форжа (`<iso>.provenance.json`) и в общий журнал.
3. Query-режим: `provenance.sh who <path>` — «откуда взялся файл» (по журналам и git).
4. Схема записи — расширение `schemas/evidence-entry.schema.json` (поле provenance)
   или отдельная схема; выбор зафиксировать в отчёте с ПОЧЕМУ.

## Границы

Разрешено: `src/lib/**`, `src/forge/**` (только вызов provenance-записи), `schemas/**`,
`tests/**`, `docs/spec/singularis/**`, CHANGELOG. Запрещено: изменение рецептов сборки
иначе как вызов записи provenance, сеть.

## Критерии приёмки

- [ ] Локальный прогон форжа (probe-фикстура) пишет .provenance.json, валидный по схеме
- [ ] who <path> на файле из прогона возвращает commit+pin+run без сети
- [ ] Тест подделки provenance (чужой hash) → обнаруживается
- [ ] verify.sh зелёный

## ПОЧЕМУ ТОЛЬКО ТАК

Фидбек N: «жёсткой связи артефакт → полный provenance нет, собирается вручную» — ручная
генеалогия не масштабируется и не проверяется. Bash, а не python: единый каркас с
ledger.sh/common.sh, ноль новых зависимостей (аксиома самодостаточности).
