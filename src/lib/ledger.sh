#!/usr/bin/env bash
# НОУС · журнал доказательств с цепочкой хешей (ADR-0011).
# Формат строки — совместим с journal коллег (Public Repo Synthesis):
#   {"seq":N,"prev":"<hash>","ts":"<iso8601>","claim":...,"status":...,
#    "method":...,"detail":...,"limitations":...,"checked_at":...,"hash":"<sha256>"}
# hash = sha256(канонический JSON строки без поля hash).
# Правка/удаление старой строки ломает все последующие хеши — ledger_verify это находит.
# Защита от небрежной правки, не от злоумышленника с доступом ко всему файлу
# (внешний якорь — git-история репо; подпись отложена, ADR-0011).

set -euo pipefail

LEDGER_GENESIS="0000000000000000000000000000000000000000000000000000000000000000"
LEDGER_STATUSES="GAP|UNKNOWN|PARTIAL|CONFIRMED|FAILED|NOT_APPLICABLE"

ledger::_json_escape() {
  # python3 обязателен для канонического JSON (уже требование pins.yaml)
  python3 - "$1" <<'PY'
import json, sys
print(json.dumps(sys.argv[1], ensure_ascii=False))
PY
}

ledger::_canon_hash() {
  # sha256 от канонического JSON (sort_keys, компактный) — как у коллег
  python3 - "$1" <<'PY'
import hashlib, json, sys
body = json.loads(sys.argv[1])
raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
print(hashlib.sha256(raw.encode("utf-8")).hexdigest())
PY
}

ledger::append() {
  # ledger_append <файл> <claim> <status> <method> <detail> [limitations]
  local file="$1" claim="$2" status="$3" method="$4" detail="$5" limitations="${6:-}"
  case "$status" in
    GAP|UNKNOWN|PARTIAL|CONFIRMED|FAILED|NOT_APPLICABLE) ;;
    *) echo "ledger: недопустимый статус '$status' (${LEDGER_STATUSES})" >&2; return 2 ;;
  esac
  local prev seq body hash ts
  if [[ -s "$file" ]]; then
    prev="$(tail -n 1 "$file" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["hash"])')"
    seq="$(($(wc -l < "$file") + 1))"
  else
    prev="$LEDGER_GENESIS"
    seq=1
  fi
  ts="$(date -u +%Y-%m-%dT%H:%M:%S.%6NZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
  local claim_j status_j method_j detail_j limit_j
  claim_j="$(ledger::_json_escape "$claim")"
  status_j="$(ledger::_json_escape "$status")"
  method_j="$(ledger::_json_escape "$method")"
  detail_j="$(ledger::_json_escape "$detail")"
  limit_j="$(ledger::_json_escape "$limitations")"
  body="{\"seq\":${seq},\"prev\":\"${prev}\",\"ts\":\"${ts}\",\"claim\":${claim_j},\"status\":${status_j},\"method\":${method_j},\"detail\":${detail_j},\"limitations\":${limit_j},\"checked_at\":\"${ts}\"}"
  hash="$(ledger::_canon_hash "$body")"
  mkdir -p "$(dirname "$file")"
  # сборка финальной строки: body + hash, запись одним append (python — канонический JSON)
  python3 - "$file" "$body" "$hash" <<'PY'
import json, sys
path, body, h = sys.argv[1], sys.argv[2], sys.argv[3]
row = json.loads(body)
row["hash"] = h
with open(path, "a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
PY
  printf '%s\n' "$hash"
}

ledger::verify() {
  # ledger_verify <файл> — exit 0: цепь целостна; exit 1: повреждена
  local file="$1"
  [[ -s "$file" ]] || { echo "журнал пуст или отсутствует: $file"; return 0; }
  python3 - "$file" <<'PY'
import hashlib, json, sys
GENESIS = "0" * 64
path = sys.argv[1]
prev = GENESIS
count = 0
with open(path, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if not line.strip():
            continue
        count += 1
        try:
            row = json.loads(line)
        except ValueError as e:
            print(f"СТРОКА {i}: не JSON ({e})"); sys.exit(1)
        if row.get("seq") != count:
            print(f"СТРОКА {i}: неверный seq ({row.get('seq')}, ожидался {count})"); sys.exit(1)
        if row.get("prev") != prev:
            print(f"СТРОКА {i}: разрыв цепочки (prev не совпадает)"); sys.exit(1)
        body = {k: v for k, v in row.items() if k != "hash"}
        raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != row.get("hash"):
            print(f"СТРОКА {i}: содержимое изменено (hash не совпадает)"); sys.exit(1)
        prev = row["hash"]
print(f"цепочка целостна ({count} записей)")
PY
}

ledger::weakest() {
  # ledger_weakest <статус1> <статус2> ... — самое слабое звено цепи (ADR-0011)
  local rank="GAP:-1 UNKNOWN:0 PARTIAL:1 CONFIRMED:2 FAILED:-1 NOT_APPLICABLE:-1"
  local worst="" worst_r=99 kv s r
  for s in "$@"; do
    for kv in $rank; do
      if [[ "$kv" == "${s}:"* ]]; then
        r="${kv#*:}"
        if (( r < worst_r )); then worst="$s"; worst_r="$r"; fi
      fi
    done
  done
  [[ -n "$worst" ]] || worst="UNKNOWN"
  printf '%s\n' "$worst"
}
