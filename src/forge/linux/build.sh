#!/usr/bin/env bash
# НОУС · src/forge/linux/build.sh — конвейер Linux-ветки форжа (спека 04, тикет 0004).
#
# Запуск:   bash src/forge/linux/build.sh <debian12|ubuntu-2404>
# Верхний уровень: bash src/forge/forge.sh <цель> (probe-гейт + вердикт, затем этот сборщик).
#
# Переменные среды:
#   NOUS_PW_HASH     — обязателен: криптохеш пароля установки (например, «openssl passwd -6»);
#                      подставляется ТОЛЬКО в момент рендера, в репо и в лог не попадает
#                      (safe-defaults: secrets_in_repo=forbidden, спека 06)
#   NOUS_USER        — имя пользователя autoinstall для ubuntu-2404 (по умолчанию: nous)
#   NOUS_HOSTNAME    — имя хоста (по умолчанию: nous-host)
#   NOUS_TARGET_DIR  — каталог артефактов (по умолчанию: <репо>/dist)
#   NOUS_ISO_PATH    — путь к уже скачанному ISO: фаза FETCH пропускается (повтор/отладка);
#                      гейты канала в таком прогоне НЕ выполняются — WARN в логе
#
# Фазы: FETCH → EXTRACT → RENDER → INJECT → BUILD → VERIFY; каждая — через nous::phase.
# Каждый сырой вывод команды идёт и в консоль, и в build-log.txt рядом с артефактом
# (аксиома «карта=территория», как Log-Raw в win-ветке). Источники — только пины
# manifests/pins.yaml (ADR-0006): ни одного URL в коде. Запись — только во временный
# каталог и NOUS_TARGET_DIR; физические носители не трогаются (safe-defaults).
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
# shellcheck source=../../lib/common.sh
source "${NOUS_ROOT}/src/lib/common.sh"

usage() {
  cat >&2 <<'EOF'
НОУС · build.sh — сборщик Linux-ISO (спека 04, тикет 0004)

Использование:
  bash src/forge/linux/build.sh <debian12|ubuntu-2404>

Цели (источники — только пины manifests/pins.yaml, секция forge:):
  debian12     Debian 12 netinst   ← пин forge.debian-netinst (ответ: preseed)
  ubuntu-2404  Ubuntu Server 24.04 ← пин forge.ubuntu-server (ответ: autoinstall/nocloud)

Переменные среды:
  NOUS_PW_HASH     (обязательна) криптохеш пароля установки; пароль не входит в репо
  NOUS_USER        имя пользователя autoinstall (по умолчанию: nous)
  NOUS_HOSTNAME    имя хоста (по умолчанию: nous-host)
  NOUS_TARGET_DIR  каталог артефактов (по умолчанию: <репо>/dist)
  NOUS_ISO_PATH    путь к готовому ISO — пропуск FETCH (повтор/отладка)
EOF
}

# --- Цель: незнакомая — usage и отказ, не тихий дрейф
[ $# -ge 1 ] || { nous::warn "цель не указана"; usage; exit 2; }
TARGET="$1"
case "${TARGET}" in
  debian12)
    PIN_KEY="forge.debian-netinst"
    SIG_NAME="SHA256SUMS.sign"   # detached-подпись SHA256SUMS в каталоге официального канала Debian
    FIND_RE='debian-12\.[0-9]+(\.[0-9]+)?-amd64-netinst\.iso'  # исполнимая форма паттерна пина
    ;;
  ubuntu-2404)
    PIN_KEY="forge.ubuntu-server"
    SIG_NAME="SHA256SUMS.gpg"    # detached-подпись SHA256SUMS в каталоге официального канала Ubuntu
    FIND_RE='ubuntu-24\.04(\.[0-9]+)?-live-server-amd64\.iso'  # исполнимая форма паттерна пина
    ;;
  *) nous::warn "незнакомая цель: ${TARGET} (допустимые: debian12, ubuntu-2404)"; usage; exit 2 ;;
esac

# --- Инструменты: честная остановка до начала работ, не отказ в середине конвейера
nous::require_tools python3 curl xorriso

# --- Каталог вывода: NOUS_TARGET_DIR/linux/<дата>; лог живёт рядом с артефактом (спека 04)
DATE_TAG="$(date +%Y-%m-%d)"
EMIT_DIR="${NOUS_TARGET_DIR}/linux/${DATE_TAG}"
mkdir -p "${EMIT_DIR}"
LOG_FILE="${EMIT_DIR}/build-log.txt"
printf '[forge] ===== прогон %s · цель %s · спека 04 =====\n' "$(date -Is)" "${TARGET}" >> "${LOG_FILE}"

# --- Временный каталог конвейера с гарантированной уборкой (операции — только temp/вывод)
WORK_DIR="$(nous::tmpdir)"
trap 'rm -rf "${WORK_DIR}"' EXIT
# Сбой мимо наших die() — тоже в лог (прямо в файл, без tee: исключаем рекурсию ловушки)
trap 'code=$?; printf "[forge] FAIL: сбой кода %s на строке %s — лог: %s\n" "${code}" "${LINENO}" "${LOG_FILE}" >> "${LOG_FILE}"' ERR

# --- Журналирование: консоль + лог одновременно; пароль/хеш в лог не печатается никогда
log()  { printf '[forge] %s\n' "$*" | tee -a "${LOG_FILE}"; }
warn() { printf '[forge] WARN: %s\n' "$*" | tee -a "${LOG_FILE}" >&2; }
die()  { printf '[forge] FAIL: %s\n' "$*" | tee -a "${LOG_FILE}" >&2; printf '[forge] лог: %s\n' "${LOG_FILE}" >&2; exit 1; }

# Сырой вывод команды → консоль и лог; код возврата сохраняется (проверяет вызывающий).
run_logged() {
  log "КОМАНДА (печатаем до исполнения): $*"
  local rc=0
  "$@" 2>&1 | tee -a "${LOG_FILE}" || rc=${PIPESTATUS[0]}
  return "${rc}"
}

# --- Значение пина: yaml-null python печатает как «None» → нормализуем в пустую строку
pin_value() {
  local raw
  raw="$(nous::pin "$1")" || die "пин ${1} недоступен (python3+pyyaml / manifests/pins.yaml)"
  if [ "${raw}" = "None" ]; then raw=""; fi
  printf '%s' "${raw}"
}

# --- Шаблоны ответов установки (спека 04): токены подставляются только в момент рендера
TEMPLATE_PRESEED="${NOUS_ROOT}/src/forge/linux/templates/debian12.preseed"
TEMPLATE_USER_DATA="${NOUS_ROOT}/src/forge/linux/templates/ubuntu-24.04/user-data"
TEMPLATE_META_DATA="${NOUS_ROOT}/src/forge/linux/templates/ubuntu-24.04/meta-data"

# Глобальные результаты фаз (фазы обмениваются фактами, не пересказом)
ISO_PATH=""; ISO_NAME=""; TREE_DIR=""; ANSWER_DIR=""; OUT_ISO=""
GPG_VERIFIED="skipped"; GPG_FPR=""; GPG_TOFU="no"

# ============================== ФАЗА FETCH ==============================
# Официальный канал → индекс → актуальный файл по пину → ISO + SHA256SUMS → сверка →
# TOFU-принуждение пина iso_sha256 → gpg-подпись (нет gpg — WARN, не отказ; спека 04).
phase_fetch() {
  if [ -n "${NOUS_ISO_PATH:-}" ]; then
    [ -f "${NOUS_ISO_PATH}" ] || die "NOUS_ISO_PATH указан, но файла нет: ${NOUS_ISO_PATH}"
    ISO_PATH="${NOUS_ISO_PATH}"
    ISO_NAME="$(basename "${ISO_PATH}")"
    warn "FETCH пропущен (NOUS_ISO_PATH): гейты канала (SHA256SUMS, подпись, пины) в этом прогоне НЕ выполнялись — происхождение образа непроверено"
    return 0
  fi

  local channel pattern
  channel="$(pin_value "${PIN_KEY}.channel")"
  pattern="$(pin_value "${PIN_KEY}.pattern")"
  [ -n "${channel}" ] || die "пин ${PIN_KEY}.channel пуст — обязательна калибровка manifests/pins.yaml"
  log "пин ${PIN_KEY}.channel = ${channel}"
  log "пин ${PIN_KEY}.pattern = ${pattern}"
  local base="${channel%/}"

  # --- 1. Индекс каталога канала; актуальный файл — исполнимая форма паттерна пина (спека 04)
  local catalog="${WORK_DIR}/catalog.html"
  if ! run_logged curl -fsSL --retry 3 "${base}/" -o "${catalog}"; then
    die "недоступен официальный канал: ${base}/ — сырой вывод выше"
  fi
  local iso_name
  iso_name="$(grep -oE "${FIND_RE}" "${catalog}" | sort -V | tail -n 1 || true)"
  [ -n "${iso_name}" ] || die "в индексе канала нет файла по паттерну пина (${pattern}) — канон канала изменился, тикет калибровки"
  log "найден актуальный образ: ${iso_name}"

  # --- 2. SHA256SUMS из того же каталога официального канала (пин checksums)
  local sums="${WORK_DIR}/SHA256SUMS"
  if ! run_logged curl -fsSL --retry 3 "${base}/SHA256SUMS" -o "${sums}"; then
    die "не скачан SHA256SUMS официального канала: ${base}/SHA256SUMS — сырой вывод выше"
  fi
  log "сырой факт — запись образа в SHA256SUMS:"
  grep -F "${iso_name}" "${sums}" | tee -a "${LOG_FILE}" || true

  # --- 3. Скачивание ISO из официального канала (спека 01: зеркалам нет)
  ISO_PATH="${WORK_DIR}/${iso_name}"
  ISO_NAME="${iso_name}"
  if ! run_logged curl -fsSL --retry 3 --retry-delay 2 "${base}/${iso_name}" -o "${ISO_PATH}"; then
    die "не скачан образ ${base}/${iso_name} — сырой вывод выше"
  fi

  # --- 4. Обязательный гейт: запись SHA256SUMS == локальный sha256, иначе отказ
  local sums_hash local_hash
  sums_hash="$(awk -v f="${iso_name}" '{ n=$2; sub(/^\*/, "", n); if (n == f) print $1 }' "${sums}")"
  [ -n "${sums_hash}" ] || die "в SHA256SUMS нет записи для ${iso_name} — структура канала изменилась"
  local_hash="$(nous::sha256 "${ISO_PATH}")"
  log "локальный sha256:      ${local_hash}"
  log "sha256 из SHA256SUMS:  ${sums_hash}"
  [ "${local_hash}" = "${sums_hash}" ] || die "SHA256 образа не совпал с официальным SHA256SUMS — отказ (спека 04)"

  # --- 5. Пин iso_sha256: не null → TOFU-принуждение (сверка с реестром обязательна)
  local pinned_hash
  pinned_hash="$(pin_value "${PIN_KEY}.iso_sha256")"
  if [ -n "${pinned_hash}" ]; then
    [ "${local_hash}" = "${pinned_hash}" ] || die "TOFU: sha256 образа не равен пину ${PIN_KEY}.iso_sha256 (${pinned_hash}) — канал подменён или пин устарел"
    log "гейт пина iso_sha256 — ОК"
  else
    log "TOFU-фиксация: ${PIN_KEY}.iso_sha256 = ${local_hash} (пин null; внести тикетом калибровки)"
  fi

  # --- 6. Подпись SHA256SUMS: gpg есть — проверяем; нет — WARN, не отказ (спека 04)
  verify_sums_signature "${base}" "${sums}"

  # --- 7. Отчёт происхождения рядом с артефактом (генеалогия; секретов в отчёте нет)
  run_logged python3 - "${EMIT_DIR}/fetch-report.json" "${TARGET}" "${PIN_KEY}" "${base}" \
    "${ISO_NAME}" "${local_hash}" "${SIG_NAME}" "${GPG_VERIFIED}" "${GPG_FPR}" "${GPG_TOFU}" <<'PY'
import json, sys
(out, target, pin, channel, iso, sha, sig, verified, fpr, tofu) = sys.argv[1:]
report = {
    "target": target,
    "pin": pin,
    "channel": channel,
    "iso_file": iso,
    "iso_sha256": sha,
    "sha256sums_verified": True,
    "gpg": {
        "sig_file": sig,
        "verified": verified == "yes",
        "fingerprint": fpr if fpr else None,
        "tofu_fixed": tofu == "yes",
    },
}
with open(out, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
PY
}

# --- Подпись SHA256SUMS (спека 04): gpg отсутствует — WARN; ключа нет в связке —
# отпечаток фиксируется (TOFU); расхождение с ненулевым пином — отказ.
verify_sums_signature() {
  local base="$1" sums="$2"
  if ! command -v gpg >/dev/null 2>&1; then
    warn "gpg не найден — криптопроверка подписи ${SIG_NAME} пропущена (гейт SHA256SUMS остаётся обязательным)"
    return 0
  fi
  local sig="${WORK_DIR}/${SIG_NAME}"
  if ! run_logged curl -fsSL --retry 3 "${base}/${SIG_NAME}" -o "${sig}"; then
    warn "не скачана подпись ${base}/${SIG_NAME} — криптопроверка пропущена; гейт SHA256SUMS остаётся"
    return 0
  fi
  local gpg_out rc=0
  gpg_out="$(gpg --batch --status-fd 1 --verify "${sig}" "${sums}" 2>&1)" || rc=$?
  printf '%s\n' "${gpg_out}" | tee -a "${LOG_FILE}"
  # Отпечаток: VALIDSIG (подпись проверена) либо ERRSIG (ключа нет в связке; новое gpg даёт fpr)
  local fpr
  fpr="$(printf '%s\n' "${gpg_out}" | awk '$2 == "VALIDSIG" { print $3; exit }')"
  if [ -z "${fpr}" ]; then
    fpr="$(printf '%s\n' "${gpg_out}" | awk '$2 == "ERRSIG" { print $9; exit }')"
  fi
  GPG_FPR="${fpr}"
  local pinned_fpr
  pinned_fpr="$(pin_value "${PIN_KEY}.key_fingerprint")"
  if [ "${rc}" -eq 0 ]; then
    GPG_VERIFIED="yes"
    log "гейт gpg: подпись SHA256SUMS действительна; отпечаток ключа: ${fpr:-<не извлечён>}"
  else
    GPG_VERIFIED="no"
    if [ -n "${fpr}" ]; then
      warn "gpg: ключа подписи нет в связке — криптопроверка НЕ выполнена; отпечаток канала: ${fpr}"
    else
      warn "gpg: верификация не удалась, отпечаток извлечь не удалось — сырой вывод выше"
    fi
  fi
  [ -n "${fpr}" ] || return 0
  if [ -n "${pinned_fpr}" ]; then
    [ "${fpr}" = "${pinned_fpr}" ] || die "TOFU: отпечаток ключа канала (${fpr}) не равен пину ${PIN_KEY}.key_fingerprint (${pinned_fpr}) — канал подменён или пин устарел"
    log "гейт пина key_fingerprint — ОК"
  else
    GPG_TOFU="yes"
    log "TOFU-фиксация: ${PIN_KEY}.key_fingerprint = ${fpr} (пин null; внести тикетом калибровки)"
  fi
}

# ============================== ФАЗА EXTRACT ==============================
phase_extract() {
  TREE_DIR="${WORK_DIR}/tree"
  mkdir -p "${TREE_DIR}"
  if ! run_logged xorriso -osirrox on -indev "${ISO_PATH}" -extract / "${TREE_DIR}"; then
    die "xorriso -extract не удался — структура образа не совпала с картой; сырой вывод выше"
  fi
  local files mib
  files="$(find "${TREE_DIR}" -type f 2>/dev/null | wc -l || true)"
  mib="$(du -sm "${TREE_DIR}" 2>/dev/null | awk '{print $1}' || true)"
  log "сырой факт: извлечено ${files:-?} файлов (${mib:-?} MiB) → ${TREE_DIR}"
}

# ============================== ФАЗА RENDER ==============================
# Токены — только из среды владельца в момент рендера; содержимое ответа (в нём хеш)
# в лог не печатается — логируются размеры (маскирование, спека 04).
phase_render() {
  [ -n "${NOUS_PW_HASH:-}" ] || die "NOUS_PW_HASH не задан — пароль не входит в репо; экспортируйте криптохеш (например: openssl passwd -6) и повторите"
  case "${TARGET}" in
    debian12)
      ANSWER_DIR="${TREE_DIR}/preseed"
      mkdir -p "${ANSWER_DIR}"
      nous::render "${TEMPLATE_PRESEED}" "${ANSWER_DIR}/debian12.preseed" "PW_HASH=${NOUS_PW_HASH}"
      ;;
    ubuntu-2404)
      ANSWER_DIR="${TREE_DIR}/nocloud"
      mkdir -p "${ANSWER_DIR}"
      nous::render "${TEMPLATE_USER_DATA}" "${ANSWER_DIR}/user-data" \
        "PW_HASH=${NOUS_PW_HASH}" "USER=${NOUS_USER:-nous}" "HOSTNAME=${NOUS_HOSTNAME:-nous-host}"
      nous::render "${TEMPLATE_META_DATA}" "${ANSWER_DIR}/meta-data"
      ;;
  esac
  local leftover f
  leftover="$(grep -RoE '__[A-Z0-9_]+__' "${ANSWER_DIR}" || true)"
  [ -z "${leftover}" ] || die "в отрендеренном ответе установки остались токены: ${leftover}"
  for f in "${ANSWER_DIR}"/*; do
    log "рендер: $(basename "${f}") → ${f} ($(stat -c '%s' "${f}") байт; содержимое в лог не печатается — хеш)"
  done
}

# ============================== ФАЗА INJECT ==============================
# Правка загрузочных конфигов дерева; цель правки не найдена — честный отказ (спека 04).
phase_inject() {
  case "${TARGET}" in
    debian12)    inject_debian ;;
    ubuntu-2404) inject_ubuntu ;;
  esac
}

# Вставка аргументов в строки «linux <kernel> …» grub.cfg; идемпотентно; 0 целей — отказ.
inject_grub_kernel_args() {
  run_logged python3 - "$1" "$2" "$3" <<'PY'
import re, sys
path, kernel, args = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8", errors="surrogateescape").read()
if args in text:
    print(f"[inject] {path}: параметры уже есть — пропуск")
    sys.exit(0)
out, hits = [], 0
for line in text.splitlines():
    if re.match(r"\s*linux\s", line) and kernel in line:
        i = line.index(kernel) + len(kernel)
        line = line[:i] + " " + args + line[i:]
        hits += 1
    out.append(line)
if hits == 0:
    sys.exit(f"FAIL: {path}: нет строк «linux … {kernel}» — цель правки не найдена")
open(path, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(out) + "\n")
print(f"[inject] {path}: правлено строк с ядром {kernel}: {hits}")
PY
}

inject_debian() {
  local cfg="${TREE_DIR}/isolinux/isolinux.cfg"
  local grub="${TREE_DIR}/boot/grub/grub.cfg"
  local kernel="/install.amd/vmlinuz" initrd="/install.amd/initrd.gz"
  local preseed_path="/cdrom/preseed/debian12.preseed"
  local args="auto=true priority=critical file=${preseed_path}"

  # --- Цели правки: конфиги загрузчиков, ядро и initrd установщика в дереве
  [ -f "${cfg}" ] || die "цель правки не найдена: ${cfg} — дерево не совпало с картой Debian 12 netinst"
  [ -f "${grub}" ] || die "цель правки не найдена: ${grub} — дерево не совпало с картой Debian 12 netinst"
  [ -f "${TREE_DIR}${kernel}" ] || die "цель правки не найдена: ядро установщика ${kernel} отсутствует в дереве"
  [ -f "${TREE_DIR}${initrd}" ] || die "цель правки не найдена: initrd установщика ${initrd} отсутствует в дереве"

  # --- isolinux.cfg: станза автозагрузки с preseed-append (спека 04)
  if grep -q "file=${preseed_path}" "${cfg}"; then
    log "isolinux.cfg: preseed уже проинжектирован — пропуск"
  else
    {
      printf '\n# НОУС · спека 04: автозагрузка установки с preseed (добавлено build.sh)\n'
      printf 'default nous-install\nprompt 0\ntimeout 1\nlabel nous-install\n'
      printf '  kernel %s\n' "${kernel}"
      printf '  append %s initrd=%s --- quiet\n' "${args}" "${initrd}"
    } >> "${cfg}"
    log "isolinux.cfg: добавлена станза nous-install (append: ${args})"
  fi
  log "сырой факт — isolinux.cfg после правки (хвост):"
  run_logged tail -n 8 "${cfg}"

  # --- grub.cfg: та же строка параметров (EFI/GRUB-загрузка, спека 04)
  if ! inject_grub_kernel_args "${grub}" "${kernel}" "${args}"; then
    die "grub.cfg: цель правки не найдена — сырой вывод выше"
  fi
  if ! run_logged grep -n "file=${preseed_path}" "${grub}"; then
    die "grub.cfg: после правки строка preseed не найдена — правка не применилась"
  fi
}

inject_ubuntu() {
  local grub="${TREE_DIR}/boot/grub/grub.cfg"
  local args='autoinstall ds=nocloud\;s=/cdrom/nocloud/'
  [ -f "${grub}" ] || die "цель правки не найдена: ${grub} — дерево не совпало с картой Ubuntu 24.04 live-server"
  [ -f "${TREE_DIR}/casper/vmlinuz" ] || die "цель правки не найдена: /casper/vmlinuz отсутствует в дереве — структура Ubuntu 24.04 изменилась"
  if ! inject_grub_kernel_args "${grub}" "/casper/vmlinuz" "${args}"; then
    die "grub.cfg: цель правки не найдена — сырой вывод выше"
  fi
  if ! run_logged grep -n "autoinstall" "${grub}"; then
    die "grub.cfg: после правки строка autoinstall не найдена — правка не применилась"
  fi
}

# ============================== ФАЗА BUILD ==============================
# xorriso-рецепт спеки 04 (двойной загрузчик BIOS+UEFI). Для ubuntu-2404 — сборка по
# ФАКТАМ дерева: полный рецепт при isolinux/; иначе GRUB-only без BIOS-флагов
# (raw-факт в лог); при наличии grub-BIOS-образа дерева — BIOS El Torito из него.
phase_build() {
  OUT_ISO="${WORK_DIR}/${ISO_NAME%.iso}-nous.iso"
  local -a xorriso_args=()

  if [ -f "${TREE_DIR}/isolinux/isolinux.bin" ] && [ -f "${TREE_DIR}/isolinux/isohdpfx.bin" ] \
     && [ -f "${TREE_DIR}/boot/grub/efi.img" ]; then
    log "сырой факт: isolinux/ + boot/grub/efi.img найдены — полный рецепт спеки 04 (BIOS+UEFI)"
    xorriso_args=( -as mkisofs -r -J -joliet-long
      -isohybrid-mbr "${TREE_DIR}/isolinux/isohdpfx.bin"
      -c isolinux/boot.cat
      -b isolinux/isolinux.bin -no-emul-boot -boot-load-size 4 -boot-info-table
      -eltorito-alt-boot -e boot/grub/efi.img -no-emul-boot
      -isohybrid-gpt-basdat
      -o "${OUT_ISO}" "${TREE_DIR}" )
  elif [ -f "${TREE_DIR}/boot/grub/efi.img" ]; then
    warn "сырой факт: isolinux/ в дереве отсутствует — сборка GRUB-only по фактам дерева"
    run_logged find "${TREE_DIR}/boot" -maxdepth 2 -print || true
    if [ -f "${TREE_DIR}/boot/grub/i386-pc/eltorito.img" ]; then
      warn "сырой факт: найден boot/grub/i386-pc/eltorito.img — BIOS El Torito из grub-образа дерева (отклонение от эталона спеки 04 по факту дерева; загрузку проверить на железе)"
      xorriso_args=( -as mkisofs -r -J -joliet-long
        -c boot/boot.cat
        -b boot/grub/i386-pc/eltorito.img -no-emul-boot -boot-load-size 4 -boot-info-table
        -eltorito-alt-boot -e boot/grub/efi.img -no-emul-boot
        -isohybrid-gpt-basdat
        -o "${OUT_ISO}" "${TREE_DIR}" )
    else
      warn "сырой факт: BIOS-образа в дереве нет — артефакт будет UEFI-only; верификатор спеки 05 (BIOS El Torito) его ОТКЛОНИТ — raw-факты выше питают тикет калибровки"
      xorriso_args=( -as mkisofs -r -J -joliet-long
        -e boot/grub/efi.img -no-emul-boot
        -isohybrid-gpt-basdat
        -o "${OUT_ISO}" "${TREE_DIR}" )
    fi
  else
    run_logged find "${TREE_DIR}" -maxdepth 2 -print || true
    die "нет загрузочных файлов дерева (ни isolinux/, ни boot/grub/efi.img) — структура образа не совпала с картой; raw-факты выше"
  fi

  if ! run_logged xorriso "${xorriso_args[@]}"; then
    die "xorriso завершился с ошибкой — сырой вывод выше"
  fi
  [ -f "${OUT_ISO}" ] || die "xorriso не создал ${OUT_ISO}"
  log "сырой факт: выход ${OUT_ISO} — $(stat -c '%s' "${OUT_ISO}") байт"
}

# ============================== ФАЗА VERIFY ==============================
# Верификатор артефакта (спека 05): BIOS+UEFI El Torito, размер, injected-файлы, SHA256SUMS.
phase_verify() {
  local final_iso="${EMIT_DIR}/${ISO_NAME%.iso}-nous.iso"
  if ! mv -- "${OUT_ISO}" "${final_iso}"; then
    die "не удалось переместить артефакт в ${final_iso}"
  fi
  local -a expected=()
  case "${TARGET}" in
    debian12)    expected=(/preseed/debian12.preseed) ;;
    ubuntu-2404) expected=(/nocloud/user-data /nocloud/meta-data) ;;
  esac
  log "вызов: bash src/lib/verify-iso.sh ${final_iso} ${expected[*]}"
  if ! run_logged bash "${NOUS_ROOT}/src/lib/verify-iso.sh" "${final_iso}" "${expected[@]}"; then
    die "верификатор спеки 05 отклонил артефакт: ${final_iso} — отчёт: ${final_iso}.eltorito-report.txt"
  fi
  # SHA256SUMS рядом с артефактом (спека 04: вывод = ISO + SHA256SUMS + лог)
  printf '%s  %s\n' "$(nous::sha256 "${final_iso}")" "$(basename "${final_iso}")" >> "${EMIT_DIR}/SHA256SUMS"
  log "SHA256SUMS дополнен: ${EMIT_DIR}/SHA256SUMS"
  log "АРТЕФАКТ: ${final_iso}"
  log "АРТЕФАКТ: размер $(stat -c '%s' "${final_iso}") байт"
  log "АРТЕФАКТ: sha256 $(nous::sha256 "${final_iso}")"
  log "ВНИМАНИЕ: реальная загрузочная проверка — первый прогон на целевом железе владельца (CI ISO не загружает)"
}

# ============================== ЗАПУСК ==============================
log "НОУС-форж · Linux-ветка · спека 04 · тикет 0004 · цель ${TARGET}"
log "репозиторий: ${NOUS_ROOT}"
log "emit (NOUS_TARGET_DIR): ${EMIT_DIR}"
log "temp: ${WORK_DIR}"
log "лог сырых команд: ${LOG_FILE}"

nous::phase "FETCH"   -- phase_fetch
log "сырой факт: ISO ${ISO_PATH} — размер $(stat -c '%s' "${ISO_PATH}") байт, sha256 $(nous::sha256 "${ISO_PATH}")"
nous::phase "EXTRACT" -- phase_extract
nous::phase "RENDER"  -- phase_render
nous::phase "INJECT"  -- phase_inject
nous::phase "BUILD"   -- phase_build
nous::phase "VERIFY"  -- phase_verify

log "готово: итог — блок АРТЕФАКТ выше; лог: ${LOG_FILE}"
