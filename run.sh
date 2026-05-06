#!/bin/bash
# run.sh - Продвинутая версия

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="run_log.txt"

# Функция для логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 Запуск скрипта загрузки"

# Проверка наличия venv
if [ ! -d "$VENV_DIR" ]; then
    log "❌ Виртуальное окружение не найдено"
    log "📦 Создаю новое виртуальное окружение..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        log "❌ Ошибка создания venv"
        exit 1
    fi
    log "✅ Виртуальное окружение создано"
fi

# Активация venv
log "🐍 Активация виртуального окружения..."
source "$VENV_DIR/bin/activate"

# Проверка и установка зависимостей
if ! python -c "import yt_dlp" 2>/dev/null; then
    log "⚠️  yt-dlp не установлен. Устанавливаю..."
    pip install --upgrade yt-dlp
fi

# Проверка наличия входного файла
if [ ! -f "playlists.txt" ]; then
    log "❌ Файл playlists.txt не найден!"
    exit 1
fi

# Запуск основного скрипта
log "🚀 Запуск YouTube Downloader..."
#python3 05_youtube_downloader.py
python3 06_youtube_downloader.py
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "✅ Скрипт завершил работу успешно"
else
    log "❌ Скрипт завершился с ошибкой (код: $EXIT_CODE)"
fi

# Деактивация
deactivate

log "🏁 Готово!"

exit $EXIT_CODE
