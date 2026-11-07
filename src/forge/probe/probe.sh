#!/usr/bin/env bash
# НОУС · src/forge/probe/probe.sh — обследование хоста строго чтением (спека 02, тикет 0002).
#
# Использование:
#   bash src/forge/probe/probe.sh [--root <каталог-фикстур>] [--out <каталог-вывода>]
#
# Что собирает (только чтение):
#   ОС/версия  — /etc/os-release, ядро (uname -r / фикстура proc/sys/kernel/osrelease);
#   CPU/RAM    — /proc/cpuinfo (модель, ядра), /proc/meminfo (MemTotal);
#   диски      — lsblk -b -o NAME,SIZE,TYPE,ROTA (JSON через -J, иначе парсинг таблицы),
#                fdisk -l — raw-приложением в журнал; в fixture-режиме — из фикстуры
#                (файл <root>/lsblk.txt с сырым выводом lsblk, если он там есть);
#   загрузка   — BIOS vs UEFI по наличию каталога /sys/firmware/efi (в fixture-режиме —
#                по наличию каталога в фикстуре);
#   ёмкости    — df -hP на / и на каталог вывода;
#   каталог    — существование, создание при отсутствии (единственная разрешённая запись
#                вне файлов отчёта), записываемость;
#   права      — id -u;
#   инструменты— command -v: xorriso, pwsh, oscdimg, gpg, python3, curl.
#
# Выход (в NOUS_TARGET_DIR или каталог из --out):
#   probe-<дата>.json — машиночитаемая карта (генерация python3, только stdlib);
#   probe-<дата>.log  — сырые команды и их выводы (аксиома 2: карта = территория).
#
# Границы записи: создание каталога вывода (если нет) и два файла отчёта — и всё.
# rm -rf, mkfs, dd, sudo, apt и любые установки отсутствуют по построению: модуль,
# отвечающий за доверие, не имеет побочных эффектов (спека 02, «ПОЧЕМУ ТОЛЬКО ТАК» п.3).
#
# Режим --root <dir> (фикстуры для CI): /etc, /proc, /sys читаются из <dir>;
# системные вызовы uname/lsblk/fdisk/df/id пропускаются с пометкой «fixture-режим»
# и значением null/unknown в JSON; исключение — домен дисков: если фикстура содержит
# <root>/lsblk.txt (подставной сырой вывод lsblk, спека 02), диски берутся из неё.
set -Eeuo pipefail

# --- Разбор аргументов ДО подключения common.sh: --out обязан попасть в
#     NOUS_TARGET_DIR заранее (common.sh фиксирует его как readonly).
PROBE_FIXTURE_ROOT=""
PROBE_OUT_OVERRIDE=""

usage_probe() {
  cat >&2 <<'EOF'
НОУС · probe — обследование хоста строго чтением (спека 02, тикет 0002)

Использование:
  bash src/forge/probe/probe.sh [--root <каталог-фикстур>] [--out <каталог-вывода>]

  --root <dir>  читать /etc, /proc, /sys из <dir> (фикстуры для CI;
                lsblk/fdisk/df/id/uname пропускаются с пометкой «fixture-режим»)
  --out  <dir>  каталог отчётов probe-<дата>.json / probe-<дата>.log
                (по умолчанию NOUS_TARGET_DIR, т.е. <репо>/dist)

Выход: машиночитаемый JSON (python3, только stdlib) + сырой журнал команд.
Модуль только читает хост; единственные записи — каталог вывода и два файла отчёта.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      if [ "$#" -lt 2 ]; then
        printf '[forge] FAIL: --root требует аргумент-каталог\n' >&2
        exit 2
      fi
      PROBE_FIXTURE_ROOT="$2"
      shift 2
      ;;
    --out)
      if [ "$#" -lt 2 ]; then
        printf '[forge] FAIL: --out требует аргумент-каталог\n' >&2
        exit 2
      fi
      PROBE_OUT_OVERRIDE="$2"
      shift 2
      ;;
    -h|--help)
      usage_probe
      exit 0
      ;;
    *)
      printf '[forge] FAIL: незнакомый аргумент probe: %s\n' "$1" >&2
      usage_probe
      exit 2
      ;;
  esac
done

# --- Корень репо из собственного пути (детерминированно, без вызова git); каркас — common.sh
PROBE_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${NOUS_ROOT:-}" ]; then
  NOUS_ROOT="$(cd "${PROBE_SELF_DIR}/../../.." && pwd)"
fi
if [ ! -f "${NOUS_ROOT}/src/lib/common.sh" ]; then
  printf '[forge] FAIL: каркас не найден: %s/src/lib/common.sh (проверьте NOUS_ROOT)\n' "${NOUS_ROOT}" >&2
  exit 1
fi
if [ -n "${PROBE_OUT_OVERRIDE}" ]; then
  NOUS_TARGET_DIR="${PROBE_OUT_OVERRIDE}"
fi
# shellcheck source=../../lib/common.sh
source "${NOUS_ROOT}/src/lib/common.sh"

# --- Фикстурный режим: карта описывает фикстуру, а не CI-машину (карта = территория)
FIXTURE_MODE="false"
if [ -n "${PROBE_FIXTURE_ROOT}" ]; then
  FIXTURE_MODE="true"
  [ -d "${PROBE_FIXTURE_ROOT}" ] || nous::die "--root: каталог-фикстур не найден: ${PROBE_FIXTURE_ROOT}"
fi

# --- Пути доменов: реальный хост или фикстура (спека 02: CI не трогает реальное железо)
if [ "${FIXTURE_MODE}" = "true" ]; then
  ETC_OS_RELEASE="${PROBE_FIXTURE_ROOT}/etc/os-release"
  PROC_CPUINFO="${PROBE_FIXTURE_ROOT}/proc/cpuinfo"
  PROC_MEMINFO="${PROBE_FIXTURE_ROOT}/proc/meminfo"
  SYS_FIRMWARE_EFI="${PROBE_FIXTURE_ROOT}/sys/firmware/efi"
  PROC_OSRELEASE="${PROBE_FIXTURE_ROOT}/proc/sys/kernel/osrelease"
else
  ETC_OS_RELEASE="/etc/os-release"
  PROC_CPUINFO="/proc/cpuinfo"
  PROC_MEMINFO="/proc/meminfo"
  SYS_FIRMWARE_EFI="/sys/firmware/efi"
  PROC_OSRELEASE="/proc/sys/kernel/osrelease"
fi

# --- Каталог вывода: ЕДИНСТВЕННАЯ разрешённая запись — создание каталога и файлов отчёта
PROBE_OUT_EXISTS="false"
PROBE_OUT_CREATED="false"
if [ -d "${NOUS_TARGET_DIR}" ]; then
  PROBE_OUT_EXISTS="true"
else
  PROBE_OUT_CREATED="true"
  nous::log "каталога вывода нет — создаю: ${NOUS_TARGET_DIR} (разрешённая запись)"
  mkdir -p "${NOUS_TARGET_DIR}" || nous::die "не удалось создать каталог вывода: ${NOUS_TARGET_DIR}"
fi
PROBE_OUT_WRITABLE="false"
if [ -w "${NOUS_TARGET_DIR}" ]; then
  PROBE_OUT_WRITABLE="true"
fi
[ "${PROBE_OUT_WRITABLE}" = "true" ] || nous::die "каталог вывода не записываем: ${NOUS_TARGET_DIR}"

# --- Артефакты дня: имя по дате, чтобы forge.sh находил «probe-отчёт текущего дня»
STAMP_DAY="$(date +%Y-%m-%d)"
STAMP_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG_FILE="${NOUS_TARGET_DIR}/probe-${STAMP_DAY}.log"
JSON_FILE="${NOUS_TARGET_DIR}/probe-${STAMP_DAY}.json"
: > "${LOG_FILE}"   # карта дня перезаписывается: актуальность важнее дублей за тот же день

# --- Пометка прерываний в журнале (ТЗ DoD: прерванная фаза не оставляет немаркированных артефактов)
trap 'printf "[probe] ПРЕРЫВАНО: строка %s, код %s\n" "${LINENO}" "$?" >> "${LOG_FILE}"' ERR

# --- Сырые записи: каждая команда фиксируется с выводом (аксиома 2), отказы нефатальны
PROBE_OUT_LAST=""
PROBE_LAST_RC=0

run_raw() {
  # Запуск команды: вывод — в журнал и в PROBE_OUT_LAST; код — в PROBE_LAST_RC.
  local label="$1"
  shift
  local rc=0
  printf '\n----- %s -----\n' "${label}" >> "${LOG_FILE}"
  PROBE_OUT_LAST="$("$@" 2>&1 | tee -a "${LOG_FILE}")" || rc=$?
  PROBE_LAST_RC="${rc}"
  if [ "${rc}" -ne 0 ]; then
    printf '[probe] НЕФАТАЛЬНО: команда завершилась с кодом %s (домен станет unknown, не ошибкой)\n' "${rc}" >> "${LOG_FILE}"
  fi
  return 0
}

raw_note() {
  # Фиксация результата проверки без внешней команды (например, [ -d ... ]).
  { printf '\n----- %s -----\n' "$1"; printf '%s\n' "$2"; } >> "${LOG_FILE}"
}

raw_skip() {
  raw_note "$1" "ПРОПУЩЕНО: fixture-режим (--root ${PROBE_FIXTURE_ROOT}) — системный вызов не выполнялся"
}

# --- Шапка журнала
if [ "${FIXTURE_MODE}" = "true" ]; then
  MODE_LINE="fixture-режим (--root: ${PROBE_FIXTURE_ROOT})"
else
  MODE_LINE="реальный-хост (только чтение)"
fi
{
  printf '=================================================================\n'
  printf 'НОУС · probe — сырой журнал обследования хоста (спека 02, тикет 0002)\n'
  printf 'дата:        %s\n' "${STAMP_ISO}"
  printf 'режим:       %s\n' "${MODE_LINE}"
  printf 'репозиторий: %s\n' "${NOUS_ROOT}"
  printf 'вывод:       %s\n' "${NOUS_TARGET_DIR}"
  printf '%s\n' '-----------------------------------------------------------------'
  printf 'Каждая секция — команда и её сырой вывод (аксиома 2); отказы помечены.\n'
  printf '=================================================================\n'
} >> "${LOG_FILE}"

nous::log "probe: режим ${MODE_LINE}; вывод ${NOUS_TARGET_DIR}"

# --- Домен OS: /etc/os-release
run_raw "домен OS: cat ${ETC_OS_RELEASE}" cat "${ETC_OS_RELEASE}"

# --- Домен arch: uname -m (в fixture-режиме смешивать архитектуру хоста с картой фикстуры нельзя)
PROBE_ARCH="unknown (fixture-режим)"
if [ "${FIXTURE_MODE}" = "true" ]; then
  raw_skip "домен arch: uname -m"
else
  run_raw "домен arch: uname -m" uname -m
  if [ "${PROBE_LAST_RC}" -eq 0 ]; then
    PROBE_ARCH="${PROBE_OUT_LAST}"
  fi
fi

# --- Домен ядро: uname -r (фикстура proc/sys/kernel/osrelease — если задана)
PROBE_KERNEL="unknown (fixture-режим)"
if [ "${FIXTURE_MODE}" = "true" ]; then
  if [ -r "${PROC_OSRELEASE}" ]; then
    run_raw "домен ядро: cat ${PROC_OSRELEASE} (фикстура)" cat "${PROC_OSRELEASE}"
    if [ "${PROBE_LAST_RC}" -eq 0 ]; then
      PROBE_KERNEL="${PROBE_OUT_LAST}"
    fi
  else
    raw_skip "домен ядро: uname -r (фикстура proc/sys/kernel/osrelease отсутствует)"
  fi
else
  run_raw "домен ядро: uname -r" uname -r
  if [ "${PROBE_LAST_RC}" -eq 0 ]; then
    PROBE_KERNEL="${PROBE_OUT_LAST}"
  fi
fi

# --- Домен CPU: /proc/cpuinfo (модель, ядра — парсит python3 при сборке JSON)
run_raw "домен CPU: cat ${PROC_CPUINFO}" cat "${PROC_CPUINFO}"

# --- Домен RAM: /proc/meminfo (MemTotal)
run_raw "домен RAM: cat ${PROC_MEMINFO}" cat "${PROC_MEMINFO}"

# --- Домен загрузка: BIOS vs UEFI по каталогу (спека 02) — проверка, не запись
PROBE_BOOT="bios"
PROBE_EFI_PRESENT="false"
if [ -d "${SYS_FIRMWARE_EFI}" ]; then
  PROBE_BOOT="uefi"
  PROBE_EFI_PRESENT="true"
fi
raw_note "домен загрузка: [ -d ${SYS_FIRMWARE_EFI} ]" \
  "результат: boot=${PROBE_BOOT}, efi_present=${PROBE_EFI_PRESENT} (только чтение каталога)"

# --- Домен диски: lsblk -J (JSON) → фолбэк на таблицу; fdisk -l — raw-приложением
PROBE_DISKS_JSON=""
PROBE_DISKS_TABLE=""
PROBE_DISKS_NOTE=""
if [ "${FIXTURE_MODE}" = "true" ]; then
  # «в fixture-режиме — из фикстуры» (тикет 0002): если фикстура несёт подставной
  # сырой вывод lsblk — парсим его (спека 02: подставные /sys-деревья И выводы команд);
  # нет — системный вызов пропускается с пометкой, домен в JSON = null (не ошибка).
  if [ -r "${PROBE_FIXTURE_ROOT}/lsblk.txt" ]; then
    run_raw "домен диски: cat ${PROBE_FIXTURE_ROOT}/lsblk.txt (фикстура: сырой вывод lsblk)" \
      cat "${PROBE_FIXTURE_ROOT}/lsblk.txt"
    if [ "${PROBE_LAST_RC}" -eq 0 ]; then
      PROBE_DISKS_TABLE="${PROBE_OUT_LAST}"
      PROBE_DISKS_NOTE="источник: фикстура lsblk.txt (сырой вывод lsblk -b -o NAME,SIZE,TYPE,ROTA)"
    fi
  else
    raw_skip "домен диски: lsblk -J -b -o NAME,SIZE,TYPE,ROTA"
    raw_skip "домен диски: fdisk -l"
    PROBE_DISKS_NOTE="lsblk/fdisk пропущены: fixture-режим; домен дисков — null (не ошибка, спека 02)"
  fi
else
  run_raw "домен диски: lsblk -J -b -o NAME,SIZE,TYPE,ROTA (JSON)" lsblk -J -b -o NAME,SIZE,TYPE,ROTA
  if [ "${PROBE_LAST_RC}" -eq 0 ] && [ -n "${PROBE_OUT_LAST}" ]; then
    PROBE_DISKS_JSON="${PROBE_OUT_LAST}"
    PROBE_DISKS_NOTE="источник: lsblk -J (JSON)"
  else
    run_raw "домен диски: lsblk -b -o NAME,SIZE,TYPE,ROTA (таблица: JSON-режим недоступен)" lsblk -b -o NAME,SIZE,TYPE,ROTA
    if [ "${PROBE_LAST_RC}" -eq 0 ]; then
      PROBE_DISKS_TABLE="${PROBE_OUT_LAST}"
      PROBE_DISKS_NOTE="источник: таблица lsblk (JSON-режим недоступен)"
    else
      PROBE_DISKS_NOTE="lsblk недоступен или ошибся — домен дисков unknown (не ошибка, спека 02)"
    fi
  fi
  if command -v fdisk >/dev/null 2>&1; then
    run_raw "домен диски: fdisk -l (raw-приложение в журнал; без root может быть частичным)" fdisk -l
  else
    raw_note "домен диски: fdisk -l" "ПРОПУЩЕНО: fdisk не найден на хосте (нефатально)"
  fi
fi

# --- Домен ёмкости: df -hP на / и на каталог вывода
PROBE_DF_ROOT=""
PROBE_DF_TARGET=""
if [ "${FIXTURE_MODE}" = "true" ]; then
  raw_skip "домен ёмкость: df -hP /"
  raw_skip "домен ёмкость: df -hP ${NOUS_TARGET_DIR}"
else
  run_raw "домен ёмкость: df -hP /" df -hP /
  if [ "${PROBE_LAST_RC}" -eq 0 ]; then
    PROBE_DF_ROOT="${PROBE_OUT_LAST}"
  fi
  run_raw "домен ёмкость: df -hP ${NOUS_TARGET_DIR}" df -hP "${NOUS_TARGET_DIR}"
  if [ "${PROBE_LAST_RC}" -eq 0 ]; then
    PROBE_DF_TARGET="${PROBE_OUT_LAST}"
  fi
fi

# --- Домен права: id -u (в fixture-режиме uid CI-машины не смешивается с картой)
PROBE_UID="unknown (fixture-режим)"
if [ "${FIXTURE_MODE}" = "true" ]; then
  raw_skip "домен права: id -u"
else
  run_raw "домен права: id -u" id -u
  if [ "${PROBE_LAST_RC}" -eq 0 ]; then
    PROBE_UID="${PROBE_OUT_LAST}"
  fi
fi

# --- Домен инструменты: command -v + версия (best effort).
# Формат спецификации: логическое-имя:бинарник:аргумент-версии ("-": версии нет).
# Перечень имён — ровно как в тикете: xorriso, pwsh, oscdimg, gpg, python3, curl.
# Проверяется БИНАРНИК (command -v gpg), а не имя пакета — иначе карта лжёт (аксиома 2).
# oscdimg — утилита Windows ADK: на Linux-хосте ожидаемо отсутствует.
PROBE_TOOLS_RECORDS=""
for spec in xorriso:xorriso:-version pwsh:pwsh:--version oscdimg:oscdimg:- gpg:gpg:--version python3:python3:--version curl:curl:--version; do
  name="${spec%%:*}"
  rest="${spec#*:}"
  bin="${rest%%:*}"
  varg="${rest#*:}"
  run_raw "домен инструменты: command -v ${bin}" command -v "${bin}"
  if [ "${PROBE_LAST_RC}" -eq 0 ]; then
    path_bin="${PROBE_OUT_LAST}"
    present="true"
    if [ "${varg}" = "-" ]; then
      ver="n/a (утилита Windows ADK)"
    else
      run_raw "домен инструменты: ${bin} ${varg}" "${bin}" "${varg}"
      if [ "${PROBE_LAST_RC}" -eq 0 ]; then
        NL=$'\n'
        ver="${PROBE_OUT_LAST%%"${NL}"*}"   # первая строка вывода версии
      else
        ver="unknown (команда версии вернула ${PROBE_LAST_RC})"
      fi
    fi
  else
    path_bin=""
    present="false"
    ver="отсутствует"
  fi
  ver="$(printf '%s' "${ver}" | tr '|' '/')"   # '|' — служебный разделитель записей
  PROBE_TOOLS_RECORDS+="name=${name}|present=${present}|path=${path_bin}|version=${ver}"$'\n'
done

# --- Вердикт forge-linux: xorriso + curl + python3 (у этой тройки бинарник = имени)
PROBE_LINUX_MISSING=""
PROBE_LINUX_SUFFICIENT="true"
for tool_name in xorriso curl python3; do
  if ! command -v "${tool_name}" >/dev/null 2>&1; then
    PROBE_LINUX_MISSING+="${tool_name} "
    PROBE_LINUX_SUFFICIENT="false"
  fi
done

# --- Машиночитаемая карта: python3, только stdlib (без внешних библиотек)
if ! command -v python3 >/dev/null 2>&1; then
  raw_note "генерация JSON" "ОШИБКА: python3 не найден — машиночитаемый выход невозможен (спека 02)"
  nous::die "python3 недоступен: генерация probe-*.json невозможна; сырой журнал сохранён: ${LOG_FILE}"
fi

export NOUS_TARGET_DIR
export PROBE_TIMESTAMP="${STAMP_ISO}" \
  PROBE_FIXTURE_MODE="${FIXTURE_MODE}" \
  PROBE_FIXTURE_ROOT="${PROBE_FIXTURE_ROOT}" \
  PROBE_OS_RELEASE="${ETC_OS_RELEASE}" \
  PROBE_CPUINFO="${PROC_CPUINFO}" \
  PROBE_MEMINFO="${PROC_MEMINFO}" \
  PROBE_KERNEL="${PROBE_KERNEL}" \
  PROBE_ARCH="${PROBE_ARCH}" \
  PROBE_BOOT="${PROBE_BOOT}" \
  PROBE_EFI_PRESENT="${PROBE_EFI_PRESENT}" \
  PROBE_UID="${PROBE_UID}" \
  PROBE_TOOLS_RECORDS="${PROBE_TOOLS_RECORDS}" \
  PROBE_DISKS_JSON="${PROBE_DISKS_JSON}" \
  PROBE_DISKS_TABLE="${PROBE_DISKS_TABLE}" \
  PROBE_DISKS_NOTE="${PROBE_DISKS_NOTE}" \
  PROBE_DF_ROOT="${PROBE_DF_ROOT}" \
  PROBE_DF_TARGET="${PROBE_DF_TARGET}" \
  PROBE_OUT_EXISTS="${PROBE_OUT_EXISTS}" \
  PROBE_OUT_CREATED="${PROBE_OUT_CREATED}" \
  PROBE_OUT_WRITABLE="${PROBE_OUT_WRITABLE}" \
  PROBE_LINUX_SUFFICIENT="${PROBE_LINUX_SUFFICIENT}" \
  PROBE_LINUX_MISSING="${PROBE_LINUX_MISSING}"

nous::log "генерация JSON-карты: ${JSON_FILE}"
if ! python3 - "${JSON_FILE}" <<'PY'
import json
import os
import re
import sys

json_path = sys.argv[1]
env = os.environ
UNKNOWN = "unknown"


def read_text(path):
    """Чтение файла домена; отсутствие файла = None (домен станет unknown, не ошибкой)."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


# --- Домен OS: /etc/os-release
os_pretty, os_id, os_version = UNKNOWN, UNKNOWN, UNKNOWN
os_release = read_text(env.get("PROBE_OS_RELEASE", ""))
if os_release:
    kv = {}
    for line in os_release.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            kv[key.strip()] = value.strip().strip('"')
    os_pretty = kv.get("PRETTY_NAME") or UNKNOWN
    os_id = kv.get("ID") or UNKNOWN
    os_version = kv.get("VERSION_ID") or UNKNOWN

# --- Домен CPU: /proc/cpuinfo (модель; логические и физические ядра)
cpu_model, cpu_cores_logical, cpu_cores_physical = UNKNOWN, None, None
cpuinfo = read_text(env.get("PROBE_CPUINFO", ""))
if cpuinfo:
    for line in cpuinfo.splitlines():
        if line.startswith("model name") and ":" in line:
            cpu_model = line.split(":", 1)[1].strip()
            break
    cpu_cores_logical = sum(1 for line in cpuinfo.splitlines() if line.startswith("processor"))
    for line in cpuinfo.splitlines():
        if line.startswith("cpu cores") and ":" in line:
            try:
                cpu_cores_physical = int(line.split(":", 1)[1].strip())
            except ValueError:
                cpu_cores_physical = None
            break

# --- Домен RAM: /proc/meminfo MemTotal
ram_gb = None
meminfo = read_text(env.get("PROBE_MEMINFO", ""))
if meminfo:
    match = re.search(r"^MemTotal:\s+(\d+)\s*kB", meminfo, re.MULTILINE)
    if match:
        ram_gb = round(int(match.group(1)) / 1024 / 1024, 2)


def disks_from_table(table):
    """Парсинг таблицы lsblk -b -o NAME,SIZE,TYPE,ROTA (фолбэк, когда -J недоступен)."""
    disks = []
    for line in (table or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[2] == "disk":
            try:
                size_gb = round(int(parts[1]) / 1024 ** 3, 2)
            except ValueError:
                size_gb = None
            rota = parts[3] == "1" if parts[3] in ("0", "1") else None
            disks.append({"name": parts[0], "size_gb": size_gb, "type": "disk", "rota": rota})
    return disks


# --- Домен диски: lsblk JSON → фолбэк на таблицу (json/re — stdlib, без внешних библиотек).
# Нет ни одного источника → null, а не []: «нет данных» не должно притворяться «дисков нет».
disks = None
raw_json = env.get("PROBE_DISKS_JSON", "")
if raw_json:
    try:
        payload = json.loads(raw_json)
        parsed = []
        for device in payload.get("blockdevices", []):
            if device.get("type") != "disk":
                continue
            size = device.get("size")
            rota = device.get("rota")
            parsed.append({
                "name": device.get("name"),
                "size_gb": round(size / 1024 ** 3, 2) if isinstance(size, int) else None,
                "type": "disk",
                "rota": bool(rota) if rota is not None else None,
            })
        disks = parsed or None
    except (ValueError, AttributeError, TypeError):
        disks = None
if not disks:
    disks = disks_from_table(env.get("PROBE_DISKS_TABLE", "")) or None


def df_avail_gb(text):
    """Свободно по df -hP: последняя строка, колонка «доступно» (например 45G, 1.8T)."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    columns = lines[-1].split()
    if len(columns) < 4:
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMGT]?)", columns[3])
    if not match:
        return None
    multiplier = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}[match.group(2)]
    return round(float(match.group(1)) * multiplier / 1024 ** 3, 2)


# --- Домен инструменты: таблица есть/нет из bash-обследования
tools = {}
for record in env.get("PROBE_TOOLS_RECORDS", "").splitlines():
    fields = dict(part.split("=", 1) for part in record.split("|") if "=" in part)
    name = fields.get("name")
    if not name:
        continue
    tools[name] = {
        "present": fields.get("present") == "true",
        "path": fields.get("path") or None,
        "version": fields.get("version") or UNKNOWN,
    }

# --- Вердикты (задача тикета: «достаточен для forge-linux?» / «достаточен для forge-win?»)
missing_linux = [item for item in env.get("PROBE_LINUX_MISSING", "").split() if item]
verdict = {
    "forge_linux": {
        "question": "достаточен для forge-linux?",
        "sufficient": env.get("PROBE_LINUX_SUFFICIENT") == "true",
        "required": ["xorriso", "curl", "python3"],
        "missing": missing_linux,
    },
    "forge_win": {
        "question": "достаточен для forge-win?",
        "sufficient": None,
        "state": "pending",
        "note": ("pwsh+oscdimg оцениваются на Windows-хосте (src/forge/forge.ps1, спека 03); "
                 "на Linux-хосте вердикт — pending по определению"),
    },
}

uid_raw = (env.get("PROBE_UID") or "").strip()
uid_value = int(uid_raw) if uid_raw.isdigit() else None

report = {
    "timestamp": env.get("PROBE_TIMESTAMP", ""),
    "probe": {
        "tool": "src/forge/probe/probe.sh",
        "ticket": "0002",
        "spec": "docs/spec/implementation/02-probe.md",
    },
    "fixture_mode": env.get("PROBE_FIXTURE_MODE") == "true",
    "fixture_root": env.get("PROBE_FIXTURE_ROOT") or None,
    "host": {
        "os": os_pretty,
        "os_id": os_id,
        "os_version": os_version,
        "arch": (env.get("PROBE_ARCH") or UNKNOWN).strip(),
        "kernel": (env.get("PROBE_KERNEL") or UNKNOWN).strip(),
        "boot": env.get("PROBE_BOOT") or UNKNOWN,
        "efi": env.get("PROBE_EFI_PRESENT") == "true",
        "boot_note": "детект по наличию каталога /sys/firmware/efi (спека 02); в контейнерах без /sys будет bios",
    },
    "resources": {
        "cpu_model": cpu_model,
        "cpu_cores": cpu_cores_logical,
        "cpu_cores_physical": cpu_cores_physical,
        "ram_gb": ram_gb,
        "disks": disks,
        "disks_note": env.get("PROBE_DISKS_NOTE") or None,
        "root_free_gb": df_avail_gb(env.get("PROBE_DF_ROOT", "")),
    },
    "network": {
        "status": UNKNOWN,
        "note": ("домен «сеть» спеки 02 (HEAD пиновых источников) — вне объёма каркасного тикета 0002; "
                 "заполняется фазой fetch (R4) после калибровки пинов (спека 01). "
                 "Отсутствующий домен = unknown, не ошибка."),
    },
    "output_dir": {
        "path": env.get("NOUS_TARGET_DIR", ""),
        "exists": env.get("PROBE_OUT_EXISTS") == "true",
        "created_by_probe": env.get("PROBE_OUT_CREATED") == "true",
        "writable": env.get("PROBE_OUT_WRITABLE") == "true",
        "free_gb": df_avail_gb(env.get("PROBE_DF_TARGET", "")),
        "uid": uid_value,
        "is_root": uid_value == 0,
    },
    "tools": tools,
    "verdict": verdict,
}

with open(json_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
then
  raw_note "генерация JSON" "ОШИБКА: python3 завершился с ошибкой; JSON-карта не записана"
  nous::die "генерация JSON не удалась (сырой вывод python3 — выше); журнал сохранён: ${LOG_FILE}"
fi

# --- Вердикт-блок на stdout: сырые значения из JSON (карта, не пересказ)
python3 - "${JSON_FILE}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
print(json.dumps({
    "report": sys.argv[1],
    "host": data["host"],
    "output_dir": data["output_dir"],
    "tools": data["tools"],
    "verdict": data["verdict"],
}, ensure_ascii=False, indent=2))
PY

# --- Итог в журнале
SUMMARY_LINUX="sufficient=${PROBE_LINUX_SUFFICIENT}"
if [ -n "${PROBE_LINUX_MISSING}" ]; then
  SUMMARY_LINUX+="; отсутствуют: ${PROBE_LINUX_MISSING}"
fi
raw_note "итог probe" "JSON-карта: ${JSON_FILE}
сырой журнал: ${LOG_FILE}
вердикт forge-linux: ${SUMMARY_LINUX}
вердикт forge-win: pending — оценивается на Windows-хосте (src/forge/forge.ps1)"

nous::log "probe завершён: JSON=${JSON_FILE} лог=${LOG_FILE}"
