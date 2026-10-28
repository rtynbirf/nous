#!/usr/bin/env bash
# НОУС · pin_action: резолв commit-SHA стороннего action для пина
# (ADR-0004). Использование: bash scripts/pin_action.sh <owner/repo> <tag>
set -euo pipefail

repo="${1:-}"
tag="${2:-}"
if [ -z "${repo}" ] || [ -z "${tag}" ]; then
  echo "usage: bash scripts/pin_action.sh <owner/repo> <tag>" >&2
  exit 1
fi

url="https://github.com/${repo}.git"

# Дереференс аннотированного тега до коммита (суффикс ^{})
sha=$(git ls-remote "${url}" "refs/tags/${tag}^{}" | awk 'NR==1{print $1}')
if [ -z "${sha}" ]; then
  # Лёгкий тег указывает на коммит напрямую
  sha=$(git ls-remote "${url}" "refs/tags/${tag}" | awk 'NR==1{print $1}')
fi

if [ -z "${sha}" ]; then
  echo "FAIL: тег ${tag} не найден в ${repo}" >&2
  exit 1
fi

if ! printf '%s' "${sha}" | grep -Eq '^[0-9a-f]{40}$'; then
  echo "FAIL: получен не 40-символьный SHA: ${sha}" >&2
  exit 1
fi

echo "${repo}@${tag} => ${sha}"
echo "Следующий шаг: внеси в .github/workflows (uses: <repo>@${sha} # ${tag}) и в manifests/pins.yaml с датой."
