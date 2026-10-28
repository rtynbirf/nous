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

echo "[state] снимок записан: ${out}"
