#!/usr/bin/env bash
# НОУС · state: снять состояние организма (эмерджентный слой).
# Использование: bash scripts/state.sh [--force]
set -euo pipefail
cd "$(dirname "$0")/.."

datestamp=$(date +%F)
out="state/snapshot-${datestamp}.md"

if [ -e "${out}" ] && [ "${1:-}" != "--force" ]; then
  echo "FAIL: ${out} существует; для перезаписи: bash scripts/state.sh --force"
  exit 1
fi

commit=$(git rev-parse HEAD)
branch=$(git rev-parse --abbrev-ref HEAD)
adr_count=$(find docs/decisions -name '*.md' -type f | wc -l | tr -d ' ')
agents=$(find .claude/agents -name '*.md' -type f | wc -l | tr -d ' ')
workflows=$(find .github/workflows -name '*.yml' -type f | wc -l | tr -d ' ')
open_tasks=$(find tasks/open -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' ')
done_tasks=$(find tasks/done -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' ')
docs_count=$(find docs -name '*.md' -type f | wc -l | tr -d ' ')
scripts_count=$(find scripts -name '*.sh' -type f | wc -l | tr -d ' ')
pyver=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')

{
  echo "# Снимок состояния НОУС — ${datestamp}"
  echo
  echo "| Метрика | Значение |"
  echo "|---|---|"
  echo "| Коммит | \`${commit}\` |"
  echo "| Ветка | ${branch} |"
  echo "| ADR | ${adr_count} |"
  echo "| Контракты субъектов | ${agents} |"
  echo "| Workflows | ${workflows} |"
  echo "| Тикеты open/done | ${open_tasks}/${done_tasks} |"
  echo "| Документов docs/ | ${docs_count} |"
  echo "| Скриптов scripts/ | ${scripts_count} |"
  echo "| Python | ${pyver} |"
} > "${out}"

# --- Машиночитаемый слой: организм читает сам себя (аксиома 6, ревизия-0 §4-C) ---
fresh_pins=$(python3 - <<'PY' 2>/dev/null || echo '{"error":"pins недоступны"}'
import json, yaml
from datetime import date, datetime
data = yaml.safe_load(open("manifests/pins.yaml", encoding="utf-8"))
today = date.today()
out = {}
for section in ("actions", "tools"):
    for name, pin in (data.get(section) or {}).items():
        checked = str(pin.get("verified_at", ""))
        age = (today - datetime.strptime(checked, "%Y-%m-%d").date()).days if checked else None
        out[f"{section}/{name}"] = {"age_days": age, "stale": bool(age is None or age >= 90)}
forge = data.get("forge") or {}
out["forge"] = {name: {"status": pin.get("status"), "sha256_fixed": bool(pin.get("iso_sha256") or pin.get("sha256"))}
                for name, pin in forge.items()}
print(json.dumps(out, ensure_ascii=False))
PY
)

cat > "state/state-${datestamp}.json" <<JSON
{
  "schema": 1,
  "generated": "${datestamp}",
  "commit": "${commit}",
  "branch": "${branch}",
  "metrics": {
    "adr": ${adr_count},
    "agent_contracts": ${agents},
    "workflows": ${workflows},
    "tasks_open": ${open_tasks},
    "tasks_done": ${done_tasks},
    "docs": ${docs_count},
    "scripts": ${scripts_count},
    "python": "${pyver}"
  },
  "pins_freshness": ${fresh_pins}
}
JSON

echo "[state] снимки записаны: ${out} + state/state-${datestamp}.json"
