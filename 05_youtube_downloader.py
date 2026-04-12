#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
YouTube Downloader for Playlists, Single Videos, and Channels
Поддерживает:
- # в начале строки -> пропуск
- [audio] в строке -> скачивание только аудио (MP3, 192kbps)
- [top=N] для канала -> N самых популярных видео
- [new=N] для канала -> N самых новых видео
- Плейлисты и отдельные видео
- Рандомные паузы между видео
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

# ========== НАСТРОЙКИ ==========
INPUT_FILE = "playlists.txt"
LOG_FILE = "download_log.txt"
YTDLP_PATH = "yt-dlp"
DOWNLOAD_ROOT = "/home/ypc/ADATA_1TB/Video_Youtube"

# ========== НАСТРОЙКИ ПАУЗ (рандомные) ==========
PAUSE_BETWEEN_VIDEOS_MIN = 2      # секунд между видео (мин)
PAUSE_BETWEEN_VIDEOS_MAX = 5      # секунд между видео (макс)
PAUSE_BETWEEN_PLAYLISTS_MIN = 3   # секунд между плейлистами/каналами (мин)
PAUSE_BETWEEN_PLAYLISTS_MAX = 8   # секунд между плейлистами/каналами (макс)

# ========== НАСТРОЙКИ АУДИО ==========
AUDIO_FORMAT = "mp3"
AUDIO_QUALITY = "192"  # kbps
# =====================================

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
    return "list=" in url or "/playlist?" in url

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
    
    # Ищем ссылку
    url_pattern = re.compile(r'https?://(?:www\.)?youtube\.com/(?:watch\?v=|playlist\?list=|@[\w\-]+|c/[\w\-]+|user/[\w\-]+)[^\s]+')
    match = url_pattern.search(clean_line)
    
    if match:
        url = match.group(0)
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

def download_single_video(video_url, download_path, filename, audio_mode, video_index=None, total_videos=None):
    """Скачивает одно видео/аудио с перерисовывающимся прогресс-баром"""
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
    
    def progress_hook(d):
        nonlocal last_update, last_line_len, final_size_mb, final_speed_mb
        
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
                    
                    # Сохраняем финальные значения
                    final_size_mb = total_mb
                    final_speed_mb = speed_mb
                    
                    progress_str = f"    ⏬ {percent:5.1f}% [{downloaded_mb:5.1f}/{total_mb:5.1f} MB] {speed_mb:4.1f} MB/s"
                    
                    sys.stdout.write('\r' + ' ' * last_line_len + '\r')
                    sys.stdout.write(progress_str)
                    sys.stdout.flush()
                    last_line_len = len(progress_str)
                    
        elif d['status'] == 'finished':
            sys.stdout.write('\r' + ' ' * last_line_len + '\r')
            sys.stdout.flush()
            print("    ✅ Готово", flush=True)
    
    if audio_mode:
        output_template = str(download_path / f"{filename}.%(ext)s")
        ydl_opts = {
            'ignoreerrors': True,
            'nooverwrites': True,
            'continuedl': True,
            'retries': 3,
            'outtmpl': output_template,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'logger': None,  # отключаем логгер
            'extractaudio': True,
            'audioformat': AUDIO_FORMAT,
            'audioquality': AUDIO_QUALITY,
        }
    else:
        output_template = str(download_path / f"{filename}.%(ext)s")
        ydl_opts = {
            'ignoreerrors': True,
            'nooverwrites': True,
            'continuedl': True,
            'retries': 3,
            'outtmpl': output_template,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'logger': None,  # отключаем логгер
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # Формируем строку статистики
        if final_size_mb > 0 and final_speed_mb > 0:
            stats_str = f"{final_size_mb:.1f} MB, {final_speed_mb:.1f} MB/s"
        elif final_size_mb > 0:
            stats_str = f"{final_size_mb:.1f} MB"
        else:
            stats_str = "статистика недоступна"
        
        return True, stats_str
        
    except Exception as e:
        print(f"\n    ✗ Ошибка: {e}")
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
    
    log_message(f"  ✓ Канал обработан")
    return True

def get_channel_name(channel_url):
    """Получает название канала по ссылке"""
    try:
        cmd = [YTDLP_PATH, "-J", "--ignore-errors", "--flat-playlist", channel_url]
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
    """Получает название канала и названия видео для одиночной ссылки"""
    try:
        cmd = [YTDLP_PATH, "-J", "--ignore-errors", video_url]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            return None, None
        data = json.loads(result.stdout)
        
        channel = data.get("channel", data.get("uploader", "UnknownChannel"))
        title = data.get("title", "UnknownVideo")
        
        # Проверяем, не является ли ссылка плейлистом
        if data.get("playlist_count"):
            playlist_title = data.get("playlist_title", data.get("title", None))
            if playlist_title:
                return channel, playlist_title, True
        
        def sanitize(name):
            return re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        
        return sanitize(channel), sanitize(title), False
    except Exception:
        return None, None, False

def main():
    log_message("=" * 70)
    log_message("🚀 ЗАПУСК СКРИПТА")
    log_message("  Поддерживает: # (комментарий), [audio], [top=N], [new=N]")
    
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
        else:
            mode_type = f"🎵 [audio]" if audio_mode else "🎬 видео"
            log_message(f"   {i}. {mode_type} | 🎬 видео | {url[:60]}...")
    
    for idx, (url, audio_mode, top_count, new_count, suffix) in enumerate(items, 1):
        log_message(f"\n--- [{idx}/{len(items)}] Обработка ---")
        log_message(f"URL: {url[:80]}...")
        
        if is_channel_url(url):
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
            # Отдельное видео
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
                        success, stats =download_single_video(url, download_path, title, audio_mode)
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