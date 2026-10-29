#!/usr/bin/env bash
# НОУС · gen_llms: сгенерировать llms.txt — плотный индекс знаний для агентов
# (конвенция llmstxt.org v2). Запускается локально и в CI (job docs).
set -euo pipefail
cd "$(dirname "$0")/.."

out="llms.txt"

title_of() {
  head -n 1 "$1" | sed 's/^# //; s/\r$//'
}

{
  echo "# НОУС"
  echo
  echo "> Эмерджентное сингулярное репо: конституция для человека и агентов, ТЗ форжа ISO, дорожная карта, контур исполнения. Язык документов — русский."
  echo
  echo "## Конституция"
  echo
  echo "- [AGENTS.md](AGENTS.md): правила субъектов, команды, железные правила, протокол тикета"
  echo "- [README](README.md): витрина, аксиомы кратко, quickstart"
  echo
  echo "## Начало"
  echo
  for f in docs/getting-started/*.md; do
    echo "- [$(title_of "${f}")](${f})"
  done
  echo
  echo "## Практика (guides)"
  echo
  for f in docs/guides/*.md; do
    echo "- [$(title_of "${f}")](${f})"
  done
  echo
  echo "## Понятия"
  echo
  for f in docs/concepts/*.md; do
    echo "- [$(title_of "${f}")](${f})"
  done
  echo
  echo "## Спеки и реализация"
  echo
  echo "- [ТЗ форжа](docs/spec/tz-nous-forge.md)"
  echo "- [Дорожная карта](docs/spec/roadmap.md)"
  for f in docs/spec/implementation/*.md; do
    echo "- [$(title_of "${f}")](${f})"
  done
  echo
  echo "## Решения (ADR)"
  echo
  for f in docs/decisions/*.md; do
    echo "- [$(title_of "${f}")](${f})"
  done
  echo
  echo "## Референс"
  echo
  for f in docs/reference/*.md; do
    echo "- [$(title_of "${f}")](${f})"
  done
  echo
} > "${out}"

echo "[gen_llms] записан ${out} ($(wc -l < "${out}" | tr -d ' ') строк)"
