#!/bin/bash
set -e

# Перейти в директорию скрипта
cd "$(dirname "$(readlink -f "$0")")" 2>/dev/null || cd "$(dirname "$0")"

# Активировать venv, если он есть
if [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

cd "$(dirname "$(readlink -f "$0")")/.." || exit 1
exec python src/ytdl.py "$@"
