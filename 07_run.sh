#!/bin/bash
# run.sh - Продвинутая версия с улучшенной обработкой ошибок и функциями

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="run_log.txt"
PID_FILE="$SCRIPT_DIR/downloader.pid"
COOKIES_FILE="$SCRIPT_DIR/cookies.txt"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функция для логирования с цветами
log() {
    local level=$1
    shift
    local message="$@"
    local color=""
    case $level in
        "INFO") color="$GREEN" ;;
        "WARN") color="$YELLOW" ;;
        "ERROR") color="$RED" ;;
        "DEBUG") color="$CYAN" ;;
        *) color="$NC" ;;
    esac
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}" | tee -a "$LOG_FILE"
}

# Функция проверки наличия команды
check_command() {
    if ! command -v $1 &> /dev/null; then
        log "ERROR" "❌ Команда '$1' не найдена"
        return 1
    fi
    return 0
}

# Функция проверки свободного места на диске
check_disk_space() {
    local path=$1
    local min_space_gb=$2
    local available=$(df -BG "$path" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available" -lt "$min_space_gb" ]; then
        log "WARN" "⚠️  Мало свободного места на диске: ${available}GB (минимум ${min_space_gb}GB)"
        return 1
    fi
    log "INFO" "💾 Свободно на диске: ${available}GB"
    return 0
}

# Функция проверки наличия PID файла
check_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log "WARN" "⚠️  Процесс уже запущен (PID: $pid)"
            return 1
        else
            rm -f "$PID_FILE"
        fi
    fi
    return 0
}

# Функция проверки cookies
check_cookies() {
    if [ -f "$COOKIES_FILE" ]; then
        log "INFO" "🍪 Файл cookies найден: $COOKIES_FILE"
        # Проверяем, не пустой ли файл
        if [ ! -s "$COOKIES_FILE" ]; then
            log "WARN" "⚠️  Файл cookies пустой!"
            return 1
        fi
        return 0
    else
        log "WARN" "⚠️  Файл cookies.txt не найден!"
        log "WARN" "    Для обхода ошибок 403 экспортируйте cookies из браузера"
        return 1
    fi
}

# Функция проверки версии Python
check_python_version() {
    local py_version=$(python3 --version 2>&1 | awk '{print $2}')
    local major=$(echo $py_version | cut -d. -f1)
    local minor=$(echo $py_version | cut -d. -f2)
    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 8 ]); then
        log "ERROR" "❌ Требуется Python 3.8+, у вас: $py_version"
        return 1
    fi
    log "INFO" "🐍 Python версия: $py_version"
    return 0
}

# Функция обновления yt-dlp
update_ytdlp() {
    log "INFO" "🔄 Обновление yt-dlp..."
    pip install --upgrade yt-dlp
    if [ $? -eq 0 ]; then
        log "INFO" "✅ yt-dlp обновлен"
        return 0
    else
        log "ERROR" "❌ Ошибка обновления yt-dlp"
        return 1
    fi
}

# Функция проверки наличия зависимостей
check_dependencies() {
    log "INFO" "📦 Проверка зависимостей..."
    
    # Проверяем наличие ffmpeg
    if ! check_command "ffmpeg"; then
        log "WARN" "⚠️  ffmpeg не найден! Видео и аудио могут не обрабатываться"
        log "WARN" "    Установите: sudo apt install ffmpeg (или эквивалент для вашей ОС)"
    else
        log "INFO" "🎬 ffmpeg найден"
    fi
    
    # Проверяем yt-dlp в Python
    if ! python -c "import yt_dlp" 2>/dev/null; then
        log "WARN" "⚠️  yt-dlp не установлен в venv. Устанавливаю..."
        pip install yt-dlp
        if [ $? -ne 0 ]; then
            log "ERROR" "❌ Не удалось установить yt-dlp"
            return 1
        fi
    fi
    
    # Проверяем другие зависимости
    local deps=("requests" "json" "subprocess" "pathlib")
    for dep in "${deps[@]}"; do
        if ! python -c "import $dep" 2>/dev/null; then
            log "WARN" "⚠️  Модуль '$dep' не найден, устанавливаю..."
            pip install $dep
        fi
    done
    
    log "INFO" "✅ Все зависимости проверены"
    return 0
}

# Функция создания директорий
create_directories() {
    local dirs=(
        "$SCRIPT_DIR/downloads"
        "$SCRIPT_DIR/logs"
        "$SCRIPT_DIR/temp"
    )
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log "INFO" "📁 Создана директория: $dir"
        fi
    done
}

# Функция показа информации о системе
show_system_info() {
    log "INFO" "=========================================="
    log "INFO" "📊 ИНФОРМАЦИЯ О СИСТЕМЕ"
    log "INFO" "=========================================="
    log "INFO" "ОС: $(uname -a)"
    log "INFO" "Свободно ОЗУ: $(free -h | awk '/^Mem:/ {print $4}')"
    log "INFO" "Диск: $(df -h . | awk 'NR==2 {print $3 " использовано из " $2 " (" $5 ")"}')"
    log "INFO" "=========================================="
}

# Функция показа справки
show_help() {
    cat << EOF
${GREEN}YouTube Downloader - Помощь${NC}

Использование:
    ./run.sh [опции]

Опции:
    ${CYAN}--help, -h${NC}         Показать эту справку
    ${CYAN}--update, -u${NC}       Принудительно обновить yt-dlp
    ${CYAN}--no-cookies${NC}       Игнорировать проверку cookies
    ${CYAN}--dry-run${NC}          Только проверка, без скачивания
    ${CYAN}--verbose, -v${NC}      Подробный вывод
    ${CYAN}--log-level LEVEL${NC}  Уровень логирования (DEBUG, INFO, WARN, ERROR)

Примеры:
    ./run.sh                    # Обычный запуск
    ./run.sh --update           # Обновить yt-dlp и запустить
    ./run.sh --dry-run          # Проверить конфигурацию
    ./run.sh --verbose          # Подробный вывод

${YELLOW}Для решения ошибки 403:${NC}
    1. Установите расширение cookies.txt для вашего браузера
    2. Экспортируйте cookies с youtube.com
    3. Сохраните как cookies.txt в папке скрипта
EOF
}

# Парсинг аргументов командной строки
DRY_RUN=false
UPDATE_ONLY=false
NO_COOKIES=false
VERBOSE=false
LOG_LEVEL="INFO"

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --update|-u)
            UPDATE_ONLY=true
            shift
            ;;
        --no-cookies)
            NO_COOKIES=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            LOG_LEVEL="DEBUG"
            shift
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        *)
            log "ERROR" "❌ Неизвестная опция: $1"
            show_help
            exit 1
            ;;
    esac
done

# Основная функция main()
main() {
    log "INFO" "🚀 ЗАПУСК YOUTUBE DOWNLOADER"
    log "INFO" "=========================================="
    
    # Проверяем PID
    if ! check_pid; then
        exit 1
    fi
    
    # Записываем PID
    echo $$ > "$PID_FILE"
    trap "rm -f $PID_FILE; exit" INT TERM EXIT
    
    # Создаем директории
    create_directories
    
    # Показываем информацию о системе
    show_system_info
    
    # Проверяем Python
    if ! check_python_version; then
        exit 1
    fi
    
    # Проверяем наличие venv
    if [ ! -d "$VENV_DIR" ]; then
        log "INFO" "📦 Создаю новое виртуальное окружение..."
        python3 -m venv venv
        if [ $? -ne 0 ]; then
            log "ERROR" "❌ Ошибка создания venv"
            exit 1
        fi
        log "INFO" "✅ Виртуальное окружение создано"
    fi
    
    # Активация venv
    log "INFO" "🐍 Активация виртуального окружения..."
    source "$VENV_DIR/bin/activate"
    
    # Проверяем зависимости
    if ! check_dependencies; then
        log "ERROR" "❌ Ошибка проверки зависимостей"
        deactivate
        exit 1
    fi
    
    # Проверяем обновления
    if $UPDATE_ONLY; then
        update_ytdlp
        deactivate
        exit $?
    fi
    
    # Проверяем наличие входного файла
    if [ ! -f "playlists.txt" ]; then
        log "ERROR" "❌ Файл playlists.txt не найден!"
        log "INFO" "📝 Создаю пример файла playlists.txt..."
        cat > playlists.txt << 'EOF'
# Пример файла playlists.txt
# Форматы:
#   # комментарий (пропускается)
#   [audio] - скачать только аудио
#   [top=N] - N самых популярных видео с канала
#   [new=N] - N самых новых видео с канала

# Обычное видео
https://www.youtube.com/watch?v=VIDEO_ID

# Аудио из видео
[audio] https://www.youtube.com/watch?v=VIDEO_ID

# Плейлист
https://www.youtube.com/playlist?list=PLAYLIST_ID

# Канал (новые видео)
[new=10] https://www.youtube.com/@CHANNEL_NAME

# Канал (популярные видео)
[top=5] https://www.youtube.com/@CHANNEL_NAME

# Шортсы
https://www.youtube.com/shorts/SHORTS_ID
EOF
        log "INFO" "✅ Создан файл playlists.txt с примерами"
        log "INFO" "📝 Отредактируйте его и запустите скрипт снова"
        deactivate
        exit 1
    fi
    
    # Проверяем cookies
    if ! $NO_COOKIES; then
        check_cookies
    fi
    
    # Проверяем свободное место (минимум 1GB)
    if ! check_disk_space "$SCRIPT_DIR" 1; then
        log "WARN" "⚠️  Недостаточно свободного места, продолжаем на свой страх и риск..."
        read -p "Продолжить? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "INFO" "⏸️  Отменено пользователем"
            deactivate
            exit 0
        fi
    fi
    
    # Выводим информацию о скачиваемых файлах
    log "INFO" "📋 Содержимое playlists.txt:"
    cat -n playlists.txt | while read line; do
        log "DEBUG" "   $line"
    done
    
    # Если dry-run, то выходим после проверки
    if $DRY_RUN; then
        log "INFO" "✅ DRY RUN - проверка завершена успешно"
        deactivate
        exit 0
    fi
    
    # Запуск основного скрипта
    log "INFO" "🚀 Запуск основного скрипта..."
    log "INFO" "=========================================="
    
    local start_time=$(date +%s)
    
    if $VERBOSE; then
        python3 07_youtube_downloader.py 2>&1 | tee -a "$LOG_FILE"
    else
        python3 07_youtube_downloader.py 2>&1 | tee -a "$LOG_FILE"
    fi
    
    local exit_code=$?
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log "INFO" "=========================================="
    log "INFO" "⏱️  Время выполнения: $((duration / 60)) минут $((duration % 60)) секунд"
    
    if [ $exit_code -eq 0 ]; then
        log "INFO" "✅ Скрипт завершил работу успешно"
    else
        log "ERROR" "❌ Скрипт завершился с ошибкой (код: $exit_code)"
        log "ERROR" "📝 Проверьте лог файл: $LOG_FILE"
        
        # Показываем последние строки лога при ошибке
        log "ERROR" "📋 Последние строки лога:"
        tail -10 "$LOG_FILE" | while read line; do
            log "ERROR" "   $line"
        done
    fi
    
    # Деактивация и удаление PID
    deactivate
    rm -f "$PID_FILE"
    
    return $exit_code
}

# Запуск с обработкой ошибок
if ! main; then
    exit 1
fi

log "INFO" "🏁 Готово!"
exit 0