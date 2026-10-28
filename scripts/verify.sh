#!/usr/bin/env bash
# НОУС · verify: сверить карту с территорией. Единая точка всех проверок.
# CI (.github/workflows/ci.yml) исполняет те же шаги по отдельности.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="python3"
[ -x .venv/bin/python ] && PY=".venv/bin/python"

status=0

echo "=== verify 1/5: исполняемая карта (unittest) ==="
"$PY" -m unittest discover -s tests -v || status=1

echo "=== verify 2/5: shellcheck (рефлексы) ==="
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck scripts/*.sh || status=1
else
  echo "WARN: shellcheck не установлен локально (в CI обязателен)"
fi

echo "=== verify 3/5: pre-commit (gitleaks + гигиена) ==="
if "$PY" -m pre_commit --version >/dev/null 2>&1; then
  "$PY" -m pre_commit run --all-files || status=1
else
  echo "WARN: pre-commit не установлен (bash scripts/bootstrap.sh)"
fi

echo "=== verify 4/5: zizmor (аудит воркфлоу) ==="
if command -v zizmor >/dev/null 2>&1; then
  zizmor --no-progress .github/workflows || status=1
else
  echo "WARN: zizmor не установлен локально (в CI обязателен)"
fi

echo "=== verify 5/5: mkdocs --strict (знание собирается) ==="
if "$PY" -c 'import mkdocs' >/dev/null 2>&1; then
  bash scripts/gen_llms.sh >/dev/null
  "$PY" -m mkdocs build --strict --site-dir .verify-site || status=1
  rm -rf .verify-site
else
  echo "WARN: mkdocs не установлен (bash scripts/bootstrap.sh)"
fi

if [ "${status}" -eq 0 ]; then
  echo "verify: OK — карта совпадает с территорией"
else
  echo "verify: FAIL — см. вывод выше; незавершённое не коммитится"
fi
exit "${status}"
