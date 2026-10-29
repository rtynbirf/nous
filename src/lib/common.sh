#!/usr/bin/env bash
# НОУС · src/lib/common.sh — общий каркас форжа (вертикаль ТЗ §2).
# Правило каталога src/forge/README.md п.3: общие части — общие модули.
# Подключение: source "${NOUS_ROOT}/src/lib/common.sh" (после NOUS_ROOT).

# --- Режим: строгий bash везде, где подключён каркас ---
set -euo pipefail

# --- Определение корня репо (git → fallback на переменную → cwd) ---
if [ -z "${NOUS_ROOT:-}" ]; then
  NOUS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
readonly NOUS_ROOT

# --- Каталог вывода артефактов (спеки 03/04: NOUS_TARGET_DIR, запись только туда) ---
NOUS_TARGET_DIR="${NOUS_TARGET_DIR:-${NOUS_ROOT}/dist}"
readonly NOUS_TARGET_DIR

nous::log()  { printf '[forge] %s\n' "$*"; }
nous::warn() { printf '[forge] WARN: %s\n' "$*" >&2; }
nous::die()  { printf '[forge] FAIL: %s\n' "$*" >&2; exit 1; }

# --- Требуемые инструменты: отсутствие = честная остановка, а не тихий дрейф ---
nous::require_tools() {
  local missing=() tool
  for tool in "$@"; do
    command -v "${tool}" >/dev/null 2>&1 || missing+=("${tool}")
  done
  [ ${#missing[@]} -eq 0 ] || nous::die "нет инструментов: ${missing[*]}; см. scripts/bootstrap.sh"
}

# --- Пины: единственный источник — manifests/pins.yaml (ADR-0006) ---
# Использование: nous::pin "forge.debian-netinst.channel"   → значение
nous::pin() {
  local path="$1"
  python3 - "$path" <<'PY'
import os, sys, yaml
path = sys.argv[1].split(".")
data = yaml.safe_load(open(os.path.join(os.environ["NOUS_ROOT"], "manifests/pins.yaml"), encoding="utf-8"))
for key in path:
    data = data[key]
print(data)
PY
}

# --- SHA256 артефакта (спека 05: каждый артефакт сопровождается суммой) ---
nous::sha256() {
  sha256sum "$1" | awk '{print $1}'
}

# --- Рендер шаблона: __TOKEN__ → значение. Неизвестный токен = отказ (карта=территория) ---
# Использование: nous::render template.in rendered.out KEY1=value1 KEY2=value2
nous::render() {
  local src="$1" dst="$2"; shift 2
  python3 - "$src" "$dst" "$@" <<'PY'
import sys, re
src, dst = sys.argv[1], sys.argv[2]
pairs = dict(a.split("=", 1) for a in sys.argv[3:])
text = open(src, encoding="utf-8").read()
tokens = set(re.findall(r"__([A-Z0-9_]+)__", text))
unknown = tokens - set(pairs)
if unknown:
    sys.exit(f"FAIL: шаблон {src} требует значения для: {sorted(unknown)}")
for key, value in pairs.items():
    text = text.replace(f"__{key}__", value)
open(dst, "w", encoding="utf-8").write(text)
PY
}

# --- Лог фазы: сырые выводы команд (аксиома 2), без секретов ---
# Использование: nous::phase "имя-фазы" -- команда с аргументами
nous::phase() {
  local name="$1"; shift
  [ "${1:-}" = "--" ] || nous::die "nous::phase: ожидается -- перед командой"
  shift
  nous::log "фаза ${name}: $*"
  "$@"
}

# --- Временный каталог с гарантированной уборкой (спеки: операции только в temp/выводе) ---
nous::tmpdir() {
  mktemp -d "${TMPDIR:-/tmp}/nous-XXXXXX"
}
