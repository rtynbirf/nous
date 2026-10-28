#!/usr/bin/env bash
# НОУС · bootstrap: восстановить среду из репо (аксиома самодостаточности).
# Идемпотентен: повторный запуск безопасен.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[bootstrap] проверка предпосылок"
command -v git >/dev/null 2>&1 || { echo "FAIL: git не найден"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "FAIL: python3 не найден"; exit 1; }

pyver=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
echo "[bootstrap] python3 = ${pyver} (минимум 3.11)"

# Изолированное окружение: не портим системный python
if [ ! -x .venv/bin/python ]; then
  echo "[bootstrap] создание .venv"
  python3 -m venv .venv
fi
PY=".venv/bin/python"

echo "[bootstrap] зависимости (requirements-dev.txt)"
"$PY" -m pip install --disable-pip-version-check --quiet --upgrade pip
"$PY" -m pip install --disable-pip-version-check --quiet -r requirements-dev.txt

echo "[bootstrap] git-хуки pre-commit"
"$PY" -m pre_commit install

echo "[bootstrap] smoke: импорт pyyaml"
"$PY" -c 'import yaml; print("[bootstrap] pyyaml", yaml.__version__)'

echo "[bootstrap] OK. Далее: bash scripts/verify.sh"
