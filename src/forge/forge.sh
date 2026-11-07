#!/usr/bin/env bash
# НОУС · src/forge/forge.sh — единая точка входа Linux-хоста (ТЗ §1).
#
# Одна команда активирует среду → обследует хост (probe) → получает дистрибутивы
# из пинов → собирает ISO → проверяет артефакты. Каждая ветка печатает сырые
# выводы; незнакомая цель — usage с перечнем целей из пинов, а не тихий дрейф.
#
# Ветка win исполняется на Windows-хосте (src/forge/forge.ps1, тикет 0003):
# здесь — честный отказ, имитации нет (ТЗ §2 п.4: ветки равноправны и раздельны).
#
# Использование: bash src/forge/forge.sh <probe|debian12|ubuntu-2404> [аргументы цели]
set -Eeuo pipefail

# --- Корень репо из собственного пути (детерминированно, без вызова git); каркас — common.sh
FORGE_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${NOUS_ROOT:-}" ]; then
  NOUS_ROOT="$(cd "${FORGE_SELF_DIR}/../.." && pwd)"
fi
if [ ! -f "${NOUS_ROOT}/src/lib/common.sh" ]; then
  printf '[forge] FAIL: каркас не найден: %s/src/lib/common.sh (проверьте NOUS_ROOT)\n' "${NOUS_ROOT}" >&2
  exit 1
fi
# shellcheck source=../lib/common.sh
source "${NOUS_ROOT}/src/lib/common.sh"

usage() {
  # Usage в stderr и exit != 0: вызов без цели — ошибка вызова, а не успешная операция.
  cat >&2 <<'EOF'
НОУС · forge — единая точка входа Linux-хоста (ТЗ §1: активировать → обследовать → получить → собрать → проверить)

Использование:
  bash src/forge/forge.sh <цель> [аргументы цели]

Цели (канонический реестр целей и источников — manifests/pins.yaml, секция forge:):
  probe        обследование хоста строго чтением (спека 02, тикет 0002)
               аргументы: [--root <каталог-фикстур>] [--out <каталог-вывода>]
  debian12     ISO Debian 12 netinst (+firmware)  ← пин forge.debian-netinst (спека 04)
  ubuntu-2404  ISO Ubuntu Server 24.04            ← пин forge.ubuntu-server (спека 04)
  win          Windows-ветка: исполняется на Windows-хосте — src/forge/forge.ps1 (спека 03, тикет 0003)

Переменные среды:
  NOUS_TARGET_DIR  каталог артефактов (по умолчанию <репо>/dist); probe-отчёт дня ищется здесь
  NOUS_ROOT        корень репо (определяется автоматически из пути скрипта)
EOF
}

forge_linux_build() {
  # Цели debian12|ubuntu-2404 (спека 04): карта до вмешательства → вердикт → сборщик.
  local target="$1"
  shift

  # --- Шаг 1. Probe-отчёт текущего дня; нет — запускам probe без аргументов
  # (аргументы цели относятся к сборке; для нестандартного каталога отчёта
  # экспортируйте NOUS_TARGET_DIR — он общий и для probe, и для этой проверки).
  local today report
  today="$(date +%Y-%m-%d)"
  report="${NOUS_TARGET_DIR}/probe-${today}.json"
  if [ ! -f "${report}" ]; then
    nous::log "probe-отчёт текущего дня (${today}) не найден — запускаю обследование (спека 02)"
    bash "${NOUS_ROOT}/src/forge/probe/probe.sh"
  fi
  [ -f "${report}" ] || nous::die "probe-отчёт не создан: ${report} — проверьте NOUS_TARGET_DIR"

  # --- Шаг 2. Вердикт-блок отчёта: сырые значения из JSON (карта, не пересказ)
  local verdict_block
  if ! verdict_block="$(python3 - "${report}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
print(json.dumps({
    "report": sys.argv[1],
    "host": data.get("host"),
    "output_dir": data.get("output_dir"),
    "tools": data.get("tools"),
    "verdict": data.get("verdict"),
}, ensure_ascii=False, indent=2))
PY
)"; then
    nous::die "probe-отчёт повреждён (невалидный JSON): ${report} — перезапустите цель probe"
  fi
  nous::log "probe-отчёт: ${report}"
  printf '%s\n' "${verdict_block}"

  # --- Шаг 3. Гейт вердикта: сборка без xorriso/curl/python3 — гарантированный
  # отказ в середине конвейера; честнее остановиться до вмешательства (ТЗ §2 п.1).
  local missing_linux
  if ! missing_linux="$(python3 - "${report}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
verdict = data.get("verdict", {}).get("forge_linux", {})
print(" ".join(verdict.get("missing", [])))
PY
)"; then
    nous::die "не удалось прочитать вердикт forge_linux из ${report}"
  fi
  if [ -n "${missing_linux}" ]; then
    nous::die "вердикт probe: forge-linux недостаточен — отсутствуют: ${missing_linux}; установите инструменты и повторите (цель probe — свежая карта)"
  fi

  # --- Шаг 4. Исполнение сборщика ветки (появляется по тикету 0004, фаза R4)
  local builder="${NOUS_ROOT}/src/forge/linux/build.sh"
  if [ ! -f "${builder}" ]; then
    nous::die "сборщик ветки ещё не реализован: src/forge/linux/build.sh отсутствует (тикет 0004, фаза R4). Карта хоста готова: ${report}"
  fi
  exec bash "${builder}" "${target}" "$@"
}

# --- Диспетчер целей
if [ "$#" -eq 0 ]; then
  nous::warn "цель не указана"
  usage
  exit 2
fi
TARGET="$1"
shift
case "${TARGET}" in
  -h|--help)
    usage
    exit 2
    ;;
  probe)
    # Прозрачный диспетчер: аргументы (--root/--out) передаются probe.sh как есть.
    exec bash "${NOUS_ROOT}/src/forge/probe/probe.sh" "$@"
    ;;
  debian12|ubuntu-2404)
    forge_linux_build "${TARGET}" "$@"
    ;;
  win)
    nous::die "Windows-ветка исполняется на Windows-хосте: см. src/forge/forge.ps1 (спека 03, тикет 0003). forge.sh — точка входа Linux-хоста; pwsh+oscdimg оцениваются forge.ps1, а не здесь."
    ;;
  *)
    nous::warn "незнакомая цель: ${TARGET} (допустимые — в usage ниже)"
    usage
    exit 2
    ;;
esac
