#!/usr/bin/env bash
# НОУС · src/scan/scan.sh — сенсор территории: анонимный скан публичных репо.
# Родословная: идея «Public Repo Synthesis» коллег (разбор — docs/genesis/
# sintez-public-repo-synthesis.md), реализация своя: bash поверх каркаса src/lib,
# цель — калибровка деталей форжа и проверка существования, не «мастерская сборки».
# Статусы (ADR-0011): GAP < UNKNOWN < PARTIAL < CONFIRMED (+FAILED, NOT_APPLICABLE).
# Доктрина секретов (ADR-0012): находки ключей фиксируются в журнале с классом A/B/C,
# НОУС не отзывает и не тестирует чужие ключи.

set -euo pipefail

NOUS_SCAN_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
# shellcheck source=../lib/common.sh
source "${NOUS_SCAN_ROOT}/src/lib/common.sh"
# shellcheck source=../lib/ledger.sh
source "${NOUS_SCAN_ROOT}/src/lib/ledger.sh"

nous::require_tools git python3

SCAN_HOSTS="github.com gitlab.com codeberg.org bitbucket.org git.sr.ht"
SCAN_JOBS=4
SCAN_OUT="${NOUS_TARGET_DIR}/scan"
SCAN_ARGS=()

scan::usage() {
  cat <<'EOF'
Использование: scan.sh [опции] <список-URL или https-URL...>
  --out DIR          каталог результатов (по умолчанию $NOUS_TARGET_DIR/scan)
  --allow-host H     добавить хост в allowlist (свои Forgejo/Gitea/GitLab)
  --jobs N           параллельность клонов (по умолчанию 4)
  --vocab FILE       словарь упоминаний: JSON {"ключ": ["подстрока", ...]}
Результат: DIR/repos.json, DIR/report.md, DIR/evidence.jsonl (цепь хешей).
Статусы: CONFIRMED — только факт (клон в чистой среде, свертка первоисточника);
PARTIAL — упоминание/наведение (всегда с методом); UNKNOWN — заявка без проверки.
EOF
}

scan::allow_host() {
  local host
  host="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$host" in
    ''|*.|.*|*..*) nous::die "некорректный хост для allowlist: '$1'" ;;
  esac
  SCAN_HOSTS="$(printf '%s\n%s' "$SCAN_HOSTS" "$host")"
}

scan::url_check() {
  # Синтаксический фильтр: только https, allowlist, без креденшелов/query.
  # Доказательство публичности — отдельной фазой (анонимный клон), не здесь.
  local url="$1"
  python3 - "$url" "$SCAN_HOSTS" <<'PY'
import sys
from urllib.parse import urlparse
url, hosts_str = sys.argv[1], sys.argv[2]
hosts = hosts_str.split()
try:
    u = urlparse(url.strip())
except ValueError:
    print("reject: ошибка разбора URL"); sys.exit(1)
host = (u.hostname or "").lower()
if u.scheme != "https":
    print(f"reject: только https (получено {u.scheme or 'нет схемы'})"); sys.exit(1)
if host not in hosts:
    print(f"reject: хост не в allowlist: {host or 'пусто'} (--allow-host)"); sys.exit(1)
if u.username or u.password:
    print("reject: учётные данные в URL запрещены (доктрина ADR-0012)"); sys.exit(1)
segs = [s for s in u.path.split("/") if s]
if len(segs) < 2:
    print("reject: нужен путь /владелец/репозиторий"); sys.exit(1)
if ".." in segs or u.query or u.fragment:
    print("reject: '..', query или fragment не принимаются"); sys.exit(1)
print("ok")
PY
}

scan::anon_env_args() {
  # Чистая среда: git физически не может использовать наши учётные данные
  # (метод коллег, проверенный их сканом 19/19; повторён и закреплён тестами у нас).
  local home="$1"
  printf 'HOME=%s\n' "$home"
  printf 'USERPROFILE=%s\n' "$home"
  printf 'XDG_CONFIG_HOME=%s\n' "$home"
  printf 'GIT_CONFIG_GLOBAL=%s\n' "/dev/null"
  printf 'GIT_CONFIG_NOSYSTEM=%s\n' "1"
  printf 'GIT_TERMINAL_PROMPT=%s\n' "0"
  printf 'GIT_SSH_COMMAND=%s\n' "false"
  printf 'GIT_ASKPASS=%s\n' ""
}

scan::clone_one() {
  # Возвращает rc; лог в $dest.log. Среда потомка: подменённые HOME/конфиги + вырезанные токены.
  local url="$1" dest="$2" workdir="$3"
  local home
  home="$(mktemp -d "${workdir}/home.XXXXXX")"
  # Вырезаем токены из окружения текущего процесса перед клоном (ADR-0012, правило 1):
  # env -i — единственный способ гарантировать чистоту; переносим только безопасные переменные.
  local safe_env=()
  local k
  for k in PATH LANG LC_ALL; do
    [[ -n "${!k:-}" ]] && safe_env+=("${k}=${!k}")
  done
  while IFS='=' read -r k v; do
    safe_env+=("${k}=${v}")
  done < <(scan::anon_env_args "$home")
  env -i "${safe_env[@]}" \
    git -c credential.helper= -c protocol.allow=never \
        -c protocol.https.allow=always -c core.hooksPath=/dev/null \
        clone --depth 1 -- "$url" "$dest" >"${dest}.log" 2>&1
}

scan::inventory() {
  # Инвентарь клона: файлы, лицензии, манифесты, тесты, упоминания (PARTIAL-наводки).
  python3 - "$1" "${2:-}" <<'PY'
import json, os, re, sys
root = sys.argv[1]
vocab_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
SKIP = {".git", "node_modules", ".venv", "venv", "vendor", "dist", "build", "__pycache__"}
MANIFESTS = {"package.json": "npm", "pyproject.toml": "python", "requirements.txt": "python-req",
             "Cargo.toml": "rust", "go.mod": "go", "pom.xml": "maven", "Gemfile": "ruby",
             "composer.json": "php", "CMakeLists.txt": "cmake", "Makefile": "make"}
files = []
for base, dirs, names in os.walk(root):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for n in names:
        files.append(os.path.relpath(os.path.join(base, n), root).replace(os.sep, "/"))
licenses = [f for f in files if os.path.basename(f).lower() in
            ("license", "licence", "copying", "license.md", "license.txt", "licence.md", "notice")]
manifests = [{"file": f, "eco": MANIFESTS[os.path.basename(f)]} for f in files if os.path.basename(f) in MANIFESTS]
tests = [f for f in files if any(p.lower() in ("test", "tests", "__tests__", "spec", "specs")
         for p in f.split("/")[:-1]) or re.search(r"(^|/)(test|spec)[^/]*\.(py|js|ts|go|rs)$", f, re.I)]
mentions = {}
if vocab_path:
    try:
        vocab = json.load(open(vocab_path, encoding="utf-8"))
    except (OSError, ValueError):
        vocab = {}
    text = ""
    for f in files:
        low = f.lower()
        if os.path.basename(low).startswith("readme") or (low.startswith("docs/") and low.endswith(".md")):
            try:
                text += open(os.path.join(root, f), encoding="utf-8", errors="replace").read(200_000).lower()
            except OSError:
                pass
    for key, needles in vocab.items():
        mentions[key] = any(n.lower() in text for n in needles)
print(json.dumps({"file_count": len(files), "licenses": licenses, "manifests": manifests,
                  "test_count": len(tests), "mentions": mentions}, ensure_ascii=False))
PY
}

scan::main() {
  local vocab=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --out) SCAN_OUT="$2"; shift 2 ;;
      --allow-host) scan::allow_host "$2"; shift 2 ;;
      --jobs) SCAN_JOBS="$2"; shift 2 ;;
      --vocab) vocab="$2"; shift 2 ;;
      -h|--help) scan::usage; exit 0 ;;
      -*) nous::die "неизвестная опция: $1 (см. scan.sh --help)" ;;
      *) SCAN_ARGS+=("$1"); shift ;;
    esac
  done
  [[ ${#SCAN_ARGS[@]} -gt 0 ]] || { scan::usage; nous::die "нет URL-списка"; }

  mkdir -p "$SCAN_OUT"
  local urls=()
  local list_file
  list_file="$(mktemp)"
  local arg
  for arg in "${SCAN_ARGS[@]}"; do
    if [[ -f "$arg" ]]; then
      grep -vE '^\s*(#|$)' "$arg" >> "$list_file"
    else
      printf '%s\n' "$arg" >> "$list_file"
    fi
  done

  local total=0 accepted=0 url reason
  while IFS= read -r url; do
    url="${url%%#*}"; url="${url//[[:space:]]/}"
    [[ -n "$url" ]] || continue
    total=$((total + 1))
    # url_check exit 1 при отказе — это ожидаемый исход, не сбой (set -e глушим)
    reason="$(scan::url_check "$url" || true)"
    if [[ "$reason" == "ok" ]]; then
      urls+=("$url"); accepted=$((accepted + 1))
    else
      echo "[scan] ОТКАЗ $url — $reason" | tee -a "$SCAN_OUT/rejected.log"
    fi
  done < "$list_file"
  rm -f "$list_file"
  [[ $accepted -gt 0 ]] || nous::die "ни один URL не принят"
  nous::log "принято $accepted из $total; клонирование (jobs=$SCAN_JOBS)..."

  local work
  work="$(mktemp -d "${NOUS_TARGET_DIR}/scan-work.XXXXXX")"

  local url name dest
  local pids=() i=0
  for url in "${urls[@]}"; do
    name="$(python3 -c "from urllib.parse import urlparse; import sys; print(urlparse(sys.argv[1]).path.strip('/').replace('/','__'))" "$url")"
    dest="${work}/${name}"
    ( scan::clone_one "$url" "$dest" "$work" ) &
    pids+=($!)
    i=$((i + 1))
    if (( i % SCAN_JOBS == 0 )); then wait "${pids[@]}" || true; pids=(); fi
  done
  (( ${#pids[@]} > 0 )) && wait "${pids[@]}" || true

  local ledger="$SCAN_OUT/evidence.jsonl"
  local jsonl="[" first=1
  for url in "${urls[@]}"; do
    name="$(python3 -c "from urllib.parse import urlparse; import sys; print(urlparse(sys.argv[1]).path.strip('/').replace('/','__'))" "$url")"
    dest="${work}/${name}"
    local repo_json status
    if [[ -d "$dest/.git" ]]; then
      local commit inv
      commit="$(git -C "$dest" rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
      inv="$(scan::inventory "$dest" "$vocab")"
      status="CONFIRMED"
      ledger::append "$ledger" "anonymous clone succeeded" CONFIRMED \
        "git clone --depth 1 в чистой среде (HOME подменён, credential.helper пуст, ssh выключен, токены вырезаны)" \
        "{\"url\":\"$url\",\"commit\":\"$commit\"}" \
        "Доказывает доступ в момент проверки; не доказывает публичность навсегда."
      local lic_count man_count test_count
      lic_count="$(python3 -c "import json,sys; print(len(json.loads(sys.argv[1])['licenses']))" "$inv")"
      man_count="$(python3 -c "import json,sys; print(len(json.loads(sys.argv[1])['manifests']))" "$inv")"
      test_count="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['test_count'])" "$inv")"
      if [[ "$lic_count" -gt 0 ]]; then
        ledger::append "$ledger" "license files detected" PARTIAL "filename inventory" \
          "{\"url\":\"$url\",\"count\":$lic_count}" "наличие файла — не разбор содержания"
      else
        ledger::append "$ledger" "license files detected" UNKNOWN "filename inventory" \
          "{\"url\":\"$url\",\"count\":0}" "файл лицензии не найден"
      fi
      if [[ "$man_count" -gt 0 ]]; then
        ledger::append "$ledger" "dependency manifests detected" PARTIAL "filename inventory" \
          "{\"url\":\"$url\",\"count\":$man_count}" "транзитивные зависимости не разрешались"
      else
        ledger::append "$ledger" "dependency manifests detected" UNKNOWN "filename inventory" \
          "{\"url\":\"$url\",\"count\":0}" "манифестов не найдено"
      fi
      ledger::append "$ledger" "security audit completed" UNKNOWN "not run" \
        "{\"url\":\"$url\",\"test_files\":$test_count}" "нужен gitleaks/OSV в изолированной среде (v0.4)"
      repo_json="{\"source_url\":\"$url\",\"status\":\"$status\",\"commit\":\"$commit\",\"inventory\":$inv}"
    else
      status="FAILED"
      repo_json="{\"source_url\":\"$url\",\"status\":\"FAILED\",\"commit\":null,\"error\":\"clone failed, лог: ${name}.log\"}"
      ledger::append "$ledger" "anonymous clone succeeded" FAILED "git clone в чистой среде" \
        "{\"url\":\"$url\"}" "см. лог клона"
    fi
    [[ $first -eq 1 ]] || jsonl+=","
    jsonl+="$repo_json"
    first=0
  done
  jsonl+="]"

  python3 - "$jsonl" "$SCAN_OUT/repos.json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PY

  # Отчёт: карта, не вердикт (аксиома 2)
  {
    echo "# Отчёт скана НОУСа"
    echo
    echo "- Дата: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- Принято/всего: ${accepted}/${total}"
    echo "- Это инвентарь и наводки, не доказательство качества и совместимости."
    echo
    echo "| Репо | Статус | Commit | Файлов | Лицензии | Манифесты |"
    echo "|---|---|---|---|---|---|"
    python3 - "$SCAN_OUT/repos.json" <<'PY'
import json, sys
for r in json.load(open(sys.argv[1], encoding="utf-8")):
    inv = r.get("inventory") or {}
    print(f"| {r['source_url']} | {r['status']} | {(r.get('commit') or '—')[:12]} "
          f"| {inv.get('file_count', '—')} | {len(inv.get('licenses', []))} | {len(inv.get('manifests', []))} |")
PY
  } > "$SCAN_OUT/report.md"

  rm -rf "$work"
  ledger::verify "$ledger"
  nous::log "готово: $SCAN_OUT/repos.json, report.md, evidence.jsonl (цепь целостна)"
}

scan::main "$@"
