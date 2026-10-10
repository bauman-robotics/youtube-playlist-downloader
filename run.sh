#!/bin/bash
set -e

# Переход в корень проекта (директория скрипта)
cd "$(dirname "$(readlink -f "$0")")"

# Читаем venv_path из config.yaml (fallback ./venv)
VENV=$(python3 -c "import yaml,sys
try:
    with open('config.yaml') as f:
        c = yaml.safe_load(f) or {}
    print(c.get('venv_path', './venv'))
except Exception:
    print('./venv')" 2>/dev/null)

if [ -z "$VENV" ]; then
    VENV="./venv"
fi

# Активируем venv, если он существует
if [ -f "$VENV/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
fi

# Без аргументов или "gui" -> GUI
if [ $# -eq 0 ] || [ "$1" = "gui" ]; then
    exec python src/gui.py
fi

# "cli" -> CLI с остальными аргументами
if [ "$1" = "cli" ]; then
    shift
    exec python src/ytdl.py "$@"
fi

# По умолчанию -> GUI
exec python src/gui.py
