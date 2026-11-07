#!/usr/bin/env bash
# НОУС · verify-iso — верификация артефакта ISO (спека 05, фаза R5).
# Субъект-владелец: forge-verifier. Общий модуль для веток win/linux.
# Использование: bash src/lib/verify-iso.sh <файл.iso> [ожидаемый-путь-в-образе ...]
# Гейты: (1) размер и сектор 2048; (2) El Torito BIOS-запись; (3) El Torito UEFI-запись;
#        (4) ожидаемые файлы внутри образа; (5) SHA256SUMS рядом с артефактом.
set -euo pipefail
cd "$(dirname "$0")/../.."

iso="${1:?использование: verify-iso.sh <файл.iso> [ожидаемый-путь ...]}"
shift || true
[ -f "${iso}" ] || { echo "FAIL: нет артефакта ${iso}" >&2; exit 1; }

status=0
say()  { printf '[verify-iso] %s\n' "$*"; }
fail() { printf '[verify-iso] FAIL: %s\n' "$*" >&2; status=1; }

command -v xorriso >/dev/null 2>&1 || { echo "FAIL: xorriso не установлен" >&2; exit 1; }

# Гейт 1: размер — реальный дистрибутив, выровненный по сектору ISO 9660 (2048)
size=$(stat -c '%s' "${iso}")
if [ "${size}" -lt 314572800 ]; then fail "размер ${size} байт меньше минимальных 300 MiB"; else say "размер: ${size} байт — ОК"; fi
if [ $(( size % 2048 )) -ne 0 ]; then fail "размер не кратен сектору 2048"; else say "сектор 2048 — ОК"; fi

# Гейты 2-3: двойная загрузочная запись (BIOS+UEFI) — инвариант спек 03/04
report=$(xorriso -indev "${iso}" -report_el_torito as_mkisofs 2>/dev/null || true)
printf '%s\n' "${report}" > "${iso}.eltorito-report.txt"
if printf '%s\n' "${report}" | grep -q -- '-b '; then say "El Torito BIOS-запись — ОК"; else fail "нет BIOS-записи El Torito"; fi
if printf '%s\n' "${report}" | grep -Eq -- '-e |isohybrid-gpt|efi'; then say "El Torito UEFI-запись — ОК"; else fail "нет UEFI-записи El Torito"; fi

# Гейт 4: ожидаемые файлы внутри образа (ответ установки и др.)
for expected in "$@"; do
  if xorriso -indev "${iso}" -find "${expected}" 2>/dev/null | grep -q .; then
    say "в образе есть ${expected} — ОК"
  else
    fail "в образе нет ${expected}"
  fi
done

# Гейт 5: контрольная сумма рядом с артефактом (генеалогия, аксиома 5)
sha256sum "${iso}" > "${iso}.sha256"
say "SHA256: $(awk '{print $1}' "${iso}.sha256")"

if [ "${status}" -eq 0 ]; then
  say "вердикт: артефакт соответствует спеке 05"
else
  say "вердикт: артефакт ОТКЛОНЁН — см. FAIL выше"
fi
exit "${status}"
