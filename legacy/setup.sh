#!/bin/bash
# setup.sh - Первоначальная настройка окружения

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🔧 Установка YouTube Downloader..."

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

# Создание venv
echo "📦 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
echo "📦 Установка зависимостей..."
pip install --upgrade pip
pip install yt-dlp ffmpeg-python

# Проверка ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  ffmpeg не найден. Установите:"
    echo "   Ubuntu/Debian: sudo apt install ffmpeg"
    echo "   MacOS: brew install ffmpeg"
    echo "   Windows: скачайте с ffmpeg.org"
fi

# Создание примера playlists.txt
if [ ! -f "playlists.txt" ]; then
    echo "📝 Создание примера playlists.txt..."
    cat > playlists.txt << 'EOF'
# YouTube Downloader - Пример файла со ссылками
# Форматы:
#   # комментарий (пропускается)
#   [audio] - скачать только аудио
#   [top=N] - N самых популярных видео с канала
#   [new=N] - N самых новых видео с канала

# Обычное видео
https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Аудио из видео
[audio] https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Плейлист
https://www.youtube.com/playlist?list=PLXXXXXXXXXXXXXXXXXX

# Канал (новые видео)
[new=10] https://www.youtube.com/@ChannelName

# Канал (популярные видео)  
[top=5] https://www.youtube.com/@ChannelName

# Шортсы
https://www.youtube.com/shorts/SHORTS_ID
EOF
fi

echo "✅ Настройка завершена!"
echo "📝 Отредактируйте playlists.txt и запустите ./run.sh"