#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
YouTube Downloader for Playlists, Single Videos, Channels, and Shorts
Поддерживает:
- # в начале строки -> пропуск
- [audio] в строке -> скачивание только аудио (MP3, 192kbps)
- [top=N] для канала -> N самых популярных видео
- [new=N] для канала -> N самых новых видео
- Плейлисты и отдельные видео
- Шортсы (YouTube Shorts)
- Рандомные паузы между видео
- Поддержка cookies для обхода 403 ошибок
"""

import re
import subprocess
import sys
import time
import random
from datetime import datetime
from pathlib import Path
import json
from urllib.parse import urlparse, parse_qs, urlunparse
import os
import argparse

# ========== НАСТРОЙКИ ==========
INPUT_FILE = "playlists.txt"
LOG_FILE = "download_log.txt"
YTDLP_PATH = "yt-dlp"
DOWNLOAD_ROOT = "/run/media/ypc/ADATA_1TB/Video_Youtube"

# Файл с cookies (экспортируйте из браузера)
COOKIES_FILE = "cookies.txt"  # Положите файл cookies.txt в папку со скриптом

# ========== НАСТРОЙКИ ПАУЗ (рандомные) ==========
PAUSE_BETWEEN_VIDEOS_MIN = 2      # секунд между видео (мин)
PAUSE_BETWEEN_VIDEOS_MAX = 5      # секунд между видео (макс)
PAUSE_BETWEEN_PLAYLISTS_MIN = 3   # секунд между плейлистами/каналами (мин)
PAUSE_BETWEEN_PLAYLISTS_MAX = 8   # секунд между плейлистами/каналами (макс)
PAUSE_BETWEEN_SINGLE_MIN = 3      # секунд между одиночными видео (мин)
PAUSE_BETWEEN_SINGLE_MAX = 7      # секунд между одиночными видео (макс)

# ========== НАСТРОЙКИ АУДИО ==========
AUDIO_FORMAT = "mp3"
AUDIO_QUALITY = "192"  # kbps
# =====================================

# Загрузка конфигурации из config.yaml (если доступен)
CONFIG_FILE = "config.yaml"
CONFIG = {}
try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                CONFIG[key.strip()] = value.strip().strip('"').strip("'")
    # Переопределяем константы из конфига, если ключи присутствуют
    if "download_root" in CONFIG:
        DOWNLOAD_ROOT = CONFIG["download_root"]
    if "input_file" in CONFIG:
        INPUT_FILE = CONFIG["input_file"]
    if "log_file" in CONFIG:
        LOG_FILE = CONFIG["log_file"]
except Exception:
    pass  # используем значения по умолчанию

def log_message(message, console=True):
    """Запись в лог и опционально в консоль"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    if console:
        print(log_entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

def is_playlist_url(url):
    """Определяет, является ли ссылка плейлистом"""
    return "list=" in url and "shorts" not in url or "/playlist?" in url

def is_channel_url(url):
    """Определяет, является ли ссылка каналом"""
    channel_patterns = [
        r'youtube\.com/@[\w\-]+',
        r'youtube\.com/c/[\w\-]+',
        r'youtube\.com/user/[\w\-]+'
    ]
    for pattern in channel_patterns:
        if re.search(pattern, url):
            return True
    return False

def is_shorts_url(url):
    """Определяет, является ли ссылка шортсом"""
    return re.search(r'youtube\.com/shorts/[a-zA-Z0-9_-]+', url) is not None

def has_audio_marker(line):
    """Проверяет, есть ли в строке маркер [audio]"""
    return re.search(r'\[audio\]', line, re.IGNORECASE) is not None

def is_commented_line(line):
    """Проверяет, начинается ли строка с # (пропуск)"""
    stripped = line.lstrip()
    return stripped.startswith("#")

def extract_channel_markers(line):
    """Извлекает [top=N] и [new=N] из строки"""
    top_match = re.search(r'\[top=(\d+)\]', line, re.IGNORECASE)
    new_match = re.search(r'\[new=(\d+)\]', line, re.IGNORECASE)
    
    top_count = int(top_match.group(1)) if top_match else None
    new_count = int(new_match.group(1)) if new_match else None
    
    return top_count, new_count

def extract_url_and_markers_from_line(line):
    """Извлекает ссылку и все маркеры"""
    # Удаляем маркеры из строки для поиска ссылки
    clean_line = re.sub(r'\[audio\]|\[top=\d+\]|\[new=\d+\]', '', line, flags=re.IGNORECASE)
    
    # Ищем ссылку (обновленный паттерн для поддержки шортсов)
    url_pattern = re.compile(r'https?://(?:www\.)?youtube\.com/(?:watch\?v=|playlist\?list=|@[\w\-]+|c/[\w\-]+|user/[\w\-]+|shorts/[a-zA-Z0-9_-]+)[^\s]*')
    match = url_pattern.search(clean_line)
    
    if match:
        url = match.group(0)
        # Очищаем URL от лишних параметров в конце
        url = re.sub(r'[&?]feature=share.*$', '', url)
        audio_mode = has_audio_marker(line)
        top_count, new_count = extract_channel_markers(line)
        return url, audio_mode, top_count, new_count
    return None, False, None, None

def extract_urls_from_file(file_path):
    """Извлекает ссылки из файла, учитывая #, [audio], [top=N], [new=N]"""
    items = []  # каждый элемент: (url, audio_mode, top_count, new_count, channel_folder_suffix)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Пропускаем закомментированные строки
                if is_commented_line(line):
                    continue
                
                url, audio_mode, top_count, new_count = extract_url_and_markers_from_line(line)
                
                if url:
                    # Для каналов определяем суффикс папки
                    channel_suffix = None
                    if is_channel_url(url):
                        if top_count:
                            channel_suffix = f"(популярные {top_count})"
                        elif new_count:
                            channel_suffix = f"(новые {new_count})"
                        else:
                            # Ссылка на канал без маркеров - пропускаем
                            log_message(f"  ⚠ Пропускаем ссылку на канал без [top=N] или [new=N]: {url[:60]}", console=True)
                            continue
                    
                    items.append((url, audio_mode, top_count, new_count, channel_suffix))
                    
    except FileNotFoundError:
        log_message(f"ОШИБКА: Файл {file_path} не найден!")
        sys.exit(1)
    
    # Удаляем дубликаты
    seen = set()
    unique_items = []
    for item in items:
        url = item[0]
        if url not in seen:
            seen.add(url)
            unique_items.append(item)
    
    return unique_items

def convert_to_playlist_url(url):
    """Преобразует watch?list=... в playlist?list=..."""
    if "list=" not in url:
        return url
    parsed = urlparse(url)
    if "watch" in parsed.path:
        query_params = parse_qs(parsed.query)
        if "list" in query_params:
            new_query = f"list={query_params['list'][0]}"
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                "/playlist",
                None,
                new_query,
                None
            ))
    return url

def get_playlist_metadata(playlist_url):
    """Получает название канала и плейлиста"""
    try:
        cmd = [YTDLP_PATH, "-J", "--ignore-errors", playlist_url]
        if os.path.exists(COOKIES_FILE):
            cmd.extend(["--cookies", COOKIES_FILE])
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        
        if result.returncode != 0:
            return None, None
        
        data = json.loads(result.stdout)
        channel = data.get("channel", data.get("uploader", None))
        playlist_title = data.get("playlist_title", data.get("title", None))
        
        if not playlist_title:
            return None, None
        
        def sanitize(name):
            return re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        
        channel = sanitize(channel) if channel else "UnknownChannel"
        playlist_title = sanitize(playlist_title)
        
        return channel, playlist_title
    except Exception:
        return None, None

def get_channel_videos(channel_url, limit=None, sort_by="date"):
    """Получает список видео с канала
    
    Args:
        channel_url: ссылка на канал
        limit: максимальное количество видео (None = все)
        sort_by: "date" (новые) или "views" (популярные)
    
    Returns:
        list of (video_url, title)
    """
    try:
        # Получаем список видео с метаданными
        cmd = [YTDLP_PATH, "--flat-playlist", "-J", "--ignore-errors", channel_url]
        if os.path.exists(COOKIES_FILE):
            cmd.extend(["--cookies", COOKIES_FILE])
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        
        if result.returncode != 0:
            log_message(f"  Ошибка получения видео с канала: {result.stderr[:200]}")
            return []
        
        data = json.loads(result.stdout)
        entries = data.get("entries", [])
        
        if not entries:
            return []
        
        # Сортируем
        if sort_by == "views":
            # По просмотрам (популярные)
            entries.sort(key=lambda x: x.get("view_count", 0), reverse=True)
        else:  # date
            # По дате (новые)
            entries.sort(key=lambda x: x.get("upload_date", ""), reverse=True)
        
        # Ограничиваем количество
        if limit and limit > 0:
            entries = entries[:limit]
        
        videos = []
        for entry in entries:
            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
            title = entry.get("title", "Unknown")
            # Очищаем название от запрещённых символов
            title = re.sub(r'[<>:"/\\|?*]', '_', title).strip()
            videos.append((video_url, title))
        
        return videos
        
    except Exception as e:
        log_message(f"  Ошибка: {e}")
        return []

def get_ytdlp_options(audio_mode, output_template):
    """Возвращает опции для yt-dlp с общими настройками"""
    # Базовые опции для всех режимов
    base_opts = {
        'quiet': True,
        'no_warnings': True,
        'logger': None,
        'ignoreerrors': True,
        'nooverwrites': True,
        'continuedl': True,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'extract_flat': False,
        'outtmpl': output_template,
    }
    
    # Добавляем cookies если файл существует
    if os.path.exists(COOKIES_FILE):
        base_opts['cookiefile'] = COOKIES_FILE
    
    # Добавляем заголовки для имитации браузера
    base_opts['headers'] = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    }
    
    # Настройки для обхода блокировок YouTube
    base_opts['extractor_args'] = {
        'youtube': {
            'skip': ['hls', 'dash'],
            'player_client': ['android', 'web'],
            'player_skip': ['webpage', 'configs'],
        }
    }
    
    if audio_mode:
        # Опции для аудио
        opts = {
            **base_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': AUDIO_FORMAT,
                'preferredquality': AUDIO_QUALITY,
            }],
        }
    else:
        # Опции для видео
        opts = {
            **base_opts,
            'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        }
    
    return opts

def download_single_video(video_url, download_path, filename, audio_mode, video_index=None, total_videos=None):
    """Скачивает одно видео/аудио с перерисовывающимся прогресс-баром"""
    # Гарантируем, что download_path - это Path
    if not isinstance(download_path, Path):
        download_path = Path(download_path)
    
    download_path.mkdir(parents=True, exist_ok=True)
    import yt_dlp
    import sys
    import logging
    
    # Отключаем логирование yt-dlp
    logging.getLogger('yt_dlp').setLevel(logging.ERROR)
    
    last_update = time.time()
    last_line_len = 0
    final_size_mb = 0
    final_speed_mb = 0
    download_success = False
    
    def progress_hook(d):
        nonlocal last_update, last_line_len, final_size_mb, final_speed_mb, download_success
        
        if d['status'] == 'downloading':
            now = time.time()
            if now - last_update >= 0.3:
                last_update = now
                
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', d.get('total_bytes_estimate', 0))
                speed = d.get('speed', 0)
                
                if total and total > 0:
                    percent = downloaded / total * 100
                    speed_mb = speed / 1024 / 1024 if speed else 0
                    downloaded_mb = downloaded / 1024 / 1024
                    total_mb = total / 1024 / 1024
                    
                    final_size_mb = total_mb
                    final_speed_mb = speed_mb
                    
                    progress_str = f"    ⏬ {percent:5.1f}% [{downloaded_mb:5.1f}/{total_mb:5.1f} MB] {speed_mb:4.1f} MB/s"
                    
                    sys.stdout.write('\r' + ' ' * last_line_len + '\r')
                    sys.stdout.write(progress_str)
                    sys.stdout.flush()
                    last_line_len = len(progress_str)
                    
        elif d['status'] == 'finished':
            download_success = True
            sys.stdout.write('\r' + ' ' * last_line_len + '\r')
            sys.stdout.flush()
            print("    ✅ Готово", flush=True)
        elif d['status'] == 'error':
            print(f"\n    ❌ Ошибка при загрузке", flush=True)
    
    # Получаем опции
    output_template = str(download_path / f"{filename}.%(ext)s")
    ydl_opts = get_ytdlp_options(audio_mode, output_template)
    ydl_opts['progress_hooks'] = [progress_hook]
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        if download_success:
            # Формируем строку статистики
            if final_size_mb > 0 and final_speed_mb > 0:
                stats_str = f"{final_size_mb:.1f} MB, {final_speed_mb:.1f} MB/s"
            elif final_size_mb > 0:
                stats_str = f"{final_size_mb:.1f} MB"
            else:
                stats_str = "статистика недоступна"
            return True, stats_str
        else:
            return False, None
        
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            print(f"\n    ❌ Ошибка 403: YouTube блокирует запрос. Попробуйте:")
            print(f"      1. Обновить yt-dlp: pip install --upgrade yt-dlp")
            print(f"      2. Экспортировать cookies из браузера в файл {COOKIES_FILE}")
            print(f"      3. Использовать VPN или изменить IP")
        else:
            print(f"\n    ❌ Ошибка: {error_msg[:200]}")
        return False, None

def download_playlist(playlist_url, channel, playlist_title, audio_mode):
    """Скачивает плейлист (видео или аудио)"""
    download_path = Path(DOWNLOAD_ROOT) / channel / playlist_title
    download_path.mkdir(parents=True, exist_ok=True)
    
    mode_str = "🎵 АУДИО (MP3)" if audio_mode else "🎬 ВИДЕО (MP4)"
    log_message(f"  📁 {channel} / {playlist_title}")
    log_message(f"  {mode_str}")
    log_message(f"  💾 Папка: {download_path}")
    
    # Получаем список видео в плейлисте
    try:
        cmd = [YTDLP_PATH, "--flat-playlist", "-J", "--ignore-errors", playlist_url]
        if os.path.exists(COOKIES_FILE):
            cmd.extend(["--cookies", COOKIES_FILE])
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        
        if result.returncode != 0:
            log_message(f"  ✗ Ошибка получения списка плейлиста")
            return False
        
        data = json.loads(result.stdout)
        entries = data.get("entries", [])
        total = len(entries)
        
        log_message(f"  📹 Видео в плейлисте: {total}")
        
        # Для плейлиста
        for idx, entry in enumerate(entries, 1):
            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
            title = entry.get("title", f"video_{idx}")
            title = re.sub(r'[<>:"/\\|?*]', '_', title).strip()
            
            log_message(f"    ↓ [{idx}/{total}] {title[:50]}...", console=True)
            success, stats = download_single_video(video_url, download_path, title, audio_mode)
            if not success:
                log_message(f"    ⚠ Ошибка при скачивании", console=True)
            else:
                log_message(f"      ✅ {stats}", console=False)
            
            # Пауза между видео в плейлисте
            if idx < total:
                pause = random.randint(PAUSE_BETWEEN_VIDEOS_MIN, PAUSE_BETWEEN_VIDEOS_MAX)
                time.sleep(pause)
        
        log_message(f"  ✓ Плейлист завершён")
        return True
        
    except Exception as e:
        log_message(f"  ✗ Ошибка: {e}")
        return False

def download_channel_videos(channel_url, channel_name, suffix, audio_mode, top_count, new_count):
    """Скачивает видео с канала (топ или новые)"""
    if top_count:
        sort_by = "views"
        limit = top_count
        folder_name = f"(популярные {top_count})"
        log_message(f"  📁 {channel_name} / {folder_name}")
        log_message(f"  🎬 ТОП-{top_count} популярных видео")
    else:
        sort_by = "date"
        limit = new_count
        folder_name = f"(новые {new_count})"
        log_message(f"  📁 {channel_name} / {folder_name}")
        log_message(f"  🎬 {new_count} самых новых видео")
    
    mode_str = "🎵 АУДИО (MP3)" if audio_mode else "🎬 ВИДЕО (MP4)"
    log_message(f"  {mode_str}")
    
    download_path = Path(DOWNLOAD_ROOT) / channel_name / folder_name
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Получаем видео
    videos = get_channel_videos(channel_url, limit=limit, sort_by=sort_by)
    
    if not videos:
        log_message(f"  ✗ Не найдено видео на канале")
        return False
    
    log_message(f"  📹 Найдено видео: {len(videos)}")
    
    for idx, (video_url, title) in enumerate(videos, 1):
        log_message(f"    ↓ [{idx}/{len(videos)}] {title[:50]}...", console=True)
        success, stats = download_single_video(video_url, download_path, title, audio_mode)
        if not success:
            log_message(f"    ⚠ Ошибка при скачивании", console=True)
        else:
            log_message(f"      ✅ {stats}", console=False)
        
        # Пауза между видео
        if idx < len(videos):
            pause = random.randint(PAUSE_BETWEEN_VIDEOS_MIN, PAUSE_BETWEEN_VIDEOS_MAX)
            time.sleep(pause)
    
    log_message(f"  ✓ Канал обработан")
    return True

def get_channel_name(channel_url):
    """Получает название канала по ссылке"""
    try:
        cmd = [YTDLP_PATH, "-J", "--ignore-errors", "--flat-playlist", channel_url]
        if os.path.exists(COOKIES_FILE):
            cmd.extend(["--cookies", COOKIES_FILE])
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            channel = data.get("channel", data.get("uploader", None))
            if channel:
                return re.sub(r'[<>:"/\\|?*]', '_', channel).strip()
    except Exception:
        pass
    return "UnknownChannel"

def get_single_metadata(video_url):
    """Получает название канала и названия видео для одиночной ссылки (включая шортсы)"""
    try:
        original_url = video_url
        
        # Для шортсов преобразуем URL в обычный watch URL
        if is_shorts_url(video_url):
            shorts_match = re.search(r'shorts/([a-zA-Z0-9_-]+)', video_url)
            if shorts_match:
                shorts_id = shorts_match.group(1)
                video_url = f"https://www.youtube.com/watch?v={shorts_id}"
                log_message(f"  → Преобразовано в обычное видео для скачивания", console=True)
        
        # Пробуем с разными клиентами
        clients = ['web', 'android', 'ios']
        data = None
        
        for client in clients:
            log_message(f"  🔍 Пробуем клиент: {client}", console=True)
            
            cmd = [YTDLP_PATH, "-J", "--ignore-errors", "--no-update"]
            
            if os.path.exists(COOKIES_FILE):
                cmd.extend(["--cookies", COOKIES_FILE])
            
            cmd.extend([
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--extractor-args", f"youtube:player_client={client}",
                "--no-check-certificates",
                video_url
            ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    if data.get('title'):  # Если есть тайтл, значит успешно
                        log_message(f"  ✅ Клиент {client} сработал", console=True)
                        break
                except:
                    continue
        
        if not data or not data.get('title'):
            # Последняя попытка - без указания клиента
            log_message(f"  🔍 Пробуем без указания клиента...", console=True)
            cmd = [YTDLP_PATH, "-J", "--ignore-errors", "--no-update"]
            if os.path.exists(COOKIES_FILE):
                cmd.extend(["--cookies", COOKIES_FILE])
            cmd.extend([
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--no-check-certificates",
                video_url
            ])
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                except:
                    pass
        
        if not data or not data.get('title'):
            log_message(f"  ✗ Не удалось получить данные ни с одним клиентом", console=True)
            return None, None, False
        
        channel = data.get("channel", data.get("uploader", "UnknownChannel"))
        title = data.get("title", "UnknownVideo")
        
        # Проверяем, не является ли ссылка плейлистом
        if data.get("playlist_count") and not is_shorts_url(original_url):
            playlist_title = data.get("playlist_title", data.get("title", None))
            if playlist_title:
                return channel, playlist_title, True
        
        def sanitize(name):
            return re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        
        log_message(f"  ✅ Получены данные: канал '{channel}', видео '{title[:50]}...'", console=True)
        return sanitize(channel), sanitize(title), False
        
    except Exception as e:
        log_message(f"  ✗ Ошибка получения метаданных: {e}", console=True)
        return None, None, False

def check_ytdlp_version():
    """Проверяет версию yt-dlp и предупреждает если она устарела"""
    try:
        result = subprocess.run([YTDLP_PATH, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            log_message(f"  📦 yt-dlp версия: {version}")
            return version
    except:
        pass
    return None

def parse_arguments():
    parser = argparse.ArgumentParser(description='YouTube Downloader')
    parser.add_argument('--no-cookies', action='store_true', help='Игнорировать cookies')
    parser.add_argument('--dry-run', action='store_true', help='Только проверка без скачивания')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    parser.add_argument('--input', '-i', default='playlists.txt', help='Файл со ссылками')
    parser.add_argument('--output', '-o', help='Директория для сохранения')
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    # Обновляем глобальные настройки если нужно
    if args.output:
        global DOWNLOAD_ROOT
        DOWNLOAD_ROOT = args.output
    
    if args.no_cookies:
        global COOKIES_FILE
        COOKIES_FILE = None

    if args.input:
        global INPUT_FILE
        INPUT_FILE = args.input

    log_message("=" * 70)
    log_message("🚀 ЗАПУСК СКРИПТА")
    log_message("  Поддерживает: # (комментарий), [audio], [top=N], [new=N], шортсы")
    
    # Проверяем версию yt-dlp
    check_ytdlp_version()
    
    # Проверяем наличие cookies
    if os.path.exists(COOKIES_FILE):
        log_message(f"  🍪 Файл cookies найден: {COOKIES_FILE}")
    else:
        log_message(f"  ⚠ Файл cookies не найден ({COOKIES_FILE})")
        log_message(f"     Для обхода ошибок 403 экспортируйте cookies из браузера")
    
    items = extract_urls_from_file(INPUT_FILE)
    
    if not items:
        log_message("❌ Не найдено ссылок!")
        sys.exit(0)
    
    log_message(f"📋 Найдено ссылок: {len(items)}")
    for i, (url, audio_mode, top_count, new_count, suffix) in enumerate(items, 1):
        if is_channel_url(url):
            if top_count:
                mode_type = f"🎵 [audio]" if audio_mode else "🎬 видео"
                log_message(f"   {i}. {mode_type} | 📺 канал [top={top_count}] | {url[:60]}...")
            else:
                mode_type = f"🎵 [audio]" if audio_mode else "🎬 видео"
                log_message(f"   {i}. {mode_type} | 📺 канал [new={new_count}] | {url[:60]}...")
        elif is_playlist_url(url):
            mode_type = f"🎵 [audio]" if audio_mode else "🎬 видео"
            log_message(f"   {i}. {mode_type} | 📂 плейлист | {url[:60]}...")
        elif is_shorts_url(url):
            mode_type = f"🎵 [audio]" if audio_mode else "🎬 видео"
            log_message(f"   {i}. {mode_type} | 📱 SHORTS | {url[:60]}...")
        else:
            mode_type = f"🎵 [audio]" if audio_mode else "🎬 видео"
            log_message(f"   {i}. {mode_type} | 🎬 видео | {url[:60]}...")
    
    for idx, (url, audio_mode, top_count, new_count, suffix) in enumerate(items, 1):
        log_message(f"\n--- [{idx}/{len(items)}] Обработка ---")
        log_message(f"URL: {url[:80]}...")
        
        # Специальная обработка для шортсов
        if is_shorts_url(url):
            log_message(f"  → Обнаружен YouTube Shorts")
            channel, title, is_playlist = get_single_metadata(url)
            
            if channel and title:
                download_path = Path(DOWNLOAD_ROOT) / channel
                file_ext = "mp3" if audio_mode else "mp4"
                video_path = download_path / f"{title}.{file_ext}"
                
                if video_path.exists():
                    log_message(f"  ℹ Уже существует, пропускаем")
                else:
                    log_message(f"  📁 {channel}")
                    mode_str = "🎵 АУДИО (MP3)" if audio_mode else "🎬 ВИДЕО (MP4)"
                    log_message(f"  {mode_str}")
                    log_message(f"  📱 Shorts: {title[:60]}")
                    success, stats = download_single_video(url, download_path, title, audio_mode)
                    if success:
                        log_message(f"      ✅ {stats}", console=False)
                
                if idx < len(items):
                    pause = random.randint(PAUSE_BETWEEN_SINGLE_MIN, PAUSE_BETWEEN_SINGLE_MAX)
                    log_message(f"  ⏸️  Пауза {pause} сек перед следующим...")
                    time.sleep(pause)
            else:
                log_message(f"  ✗ Не удалось получить данные для шортса")
        
        elif is_channel_url(url):
            # Ссылка на канал
            channel_name = get_channel_name(url)
            if not channel_name:
                log_message(f"  ✗ Не удалось получить название канала")
                continue
            
            log_message(f"  → Канал: {channel_name}")
            
            # Проверяем, не скачан ли уже
            if top_count:
                folder_name = f"(популярные {top_count})"
            else:
                folder_name = f"(новые {new_count})"
            
            channel_path = Path(DOWNLOAD_ROOT) / channel_name / folder_name
            if channel_path.exists() and any(channel_path.iterdir()):
                log_message(f"  ℹ Уже существует, пропускаем")
            else:
                download_channel_videos(url, channel_name, suffix, audio_mode, top_count, new_count)
            
            if idx < len(items):
                pause = random.randint(PAUSE_BETWEEN_PLAYLISTS_MIN, PAUSE_BETWEEN_PLAYLISTS_MAX)
                log_message(f"  ⏸️  Пауза {pause} сек перед следующим...")
                time.sleep(pause)
                
        elif is_playlist_url(url):
            # Плейлист
            clean_url = convert_to_playlist_url(url)
            channel, playlist_title = get_playlist_metadata(clean_url)
            
            if channel and playlist_title:
                playlist_path = Path(DOWNLOAD_ROOT) / channel / playlist_title
                if playlist_path.exists() and any(playlist_path.iterdir()):
                    log_message(f"  ℹ Уже существует, пропускаем")
                else:
                    download_playlist(clean_url, channel, playlist_title, audio_mode)
                
                if idx < len(items):
                    pause = random.randint(PAUSE_BETWEEN_PLAYLISTS_MIN, PAUSE_BETWEEN_PLAYLISTS_MAX)
                    log_message(f"  ⏸️  Пауза {pause} сек перед следующим...")
                    time.sleep(pause)
            else:
                log_message(f"  ✗ Не удалось получить данные")
        else:
            # Отдельное видео (обычное)
            channel, title, is_playlist = get_single_metadata(url)
            
            if channel and title:
                if is_playlist:
                    # Ссылка оказалась плейлистом
                    log_message(f"  → Обнаружен плейлист, переключаю режим")
                    playlist_path = Path(DOWNLOAD_ROOT) / channel / title
                    if playlist_path.exists() and any(playlist_path.iterdir()):
                        log_message(f"  ℹ Уже существует, пропускаем")
                    else:
                        download_playlist(url, channel, title, audio_mode)
                else:
                    # Обычное одиночное видео
                    download_path = Path(DOWNLOAD_ROOT) / channel
                    file_ext = "mp3" if audio_mode else "mp4"
                    video_path = download_path / f"{title}.{file_ext}"
                    
                    if video_path.exists():
                        log_message(f"  ℹ Уже существует, пропускаем")
                    else:
                        log_message(f"  📁 {channel}")
                        mode_str = "🎵 АУДИО (MP3)" if audio_mode else "🎬 ВИДЕО (MP4)"
                        log_message(f"  {mode_str}")
                        log_message(f"  🎬 {title[:60]}")
                        success, stats = download_single_video(url, download_path, title, audio_mode)
                        if success:
                            log_message(f"      ✅ {stats}", console=False)
                
                if idx < len(items) and not is_playlist:
                    pause = random.randint(PAUSE_BETWEEN_SINGLE_MIN, PAUSE_BETWEEN_SINGLE_MAX)
                    log_message(f"  ⏸️  Пауза {pause} сек...")
                    time.sleep(pause)
            else:
                log_message(f"  ✗ Не удалось получить данные")
    
    log_message("\n" + "=" * 70)
    log_message("✅ ГОТОВО")


if __name__ == "__main__":
    main()