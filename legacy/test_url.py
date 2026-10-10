#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Диагностический скрипт для проверки URL
"""

import subprocess
import json
import sys
import os
import shutil

def find_ytdlp():
    """Находит путь к yt-dlp"""
    ytdlp = shutil.which("yt-dlp")
    if ytdlp:
        return ytdlp
    
    venv_paths = [
        "./venv/bin/yt-dlp",
        "../venv/bin/yt-dlp",
        "~/venv/bin/yt-dlp"
    ]
    for path in venv_paths:
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded) and os.access(expanded, os.X_OK):
            return expanded
    
    system_paths = [
        "/usr/local/bin/yt-dlp",
        "/usr/bin/yt-dlp"
    ]
    for path in system_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    
    return "yt-dlp"

def get_ytdlp_version(ytdlp_path):
    """Получает версию yt-dlp"""
    try:
        cmd = [ytdlp_path, "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "Неизвестно"

def test_url(url):
    print(f"🔍 Тестирование URL: {url}")
    print("=" * 60)
    
    ytdlp = find_ytdlp()
    print(f"📦 Используется yt-dlp: {ytdlp}")
    
    # Проверяем версию
    version = get_ytdlp_version(ytdlp)
    print(f"📦 Версия yt-dlp: {version}")
    
    # Проверяем, не устарела ли версия
    try:
        if version != "Неизвестно":
            ver_parts = version.split('.')
            if len(ver_parts) == 3:
                import datetime
                ver_date = datetime.datetime(int(ver_parts[0]), int(ver_parts[1]), int(ver_parts[2]))
                days_old = (datetime.datetime.now() - ver_date).days
                if days_old > 30:
                    print(f"⚠️  Версия устарела ({days_old} дней). Рекомендуется обновить!")
                    print("   Выполните: pip install --upgrade yt-dlp")
    except:
        pass
    
    print("-" * 60)
    
    # Проверяем наличие cookies
    cookies_exist = os.path.exists("cookies.txt")
    print(f"🍪 Файл cookies.txt: {'✅ найден' if cookies_exist else '❌ не найден'}")
    
    # Пробуем разные методы
    methods = [
        {
            "name": "Метод 1: Без cookies, стандартный",
            "cmd": [
                ytdlp,
                "--no-check-certificates",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "-J",
                "--ignore-errors",
                "--no-update",
                url
            ]
        },
        {
            "name": "Метод 2: С cookies, стандартный",
            "cmd": [
                ytdlp,
                "--cookies", "cookies.txt",
                "--no-check-certificates",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "-J",
                "--ignore-errors",
                "--no-update",
                url
            ]
        },
        {
            "name": "Метод 3: Только web клиент",
            "cmd": [
                ytdlp,
                "--no-check-certificates",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--extractor-args", "youtube:player_client=web",
                "-J",
                "--ignore-errors",
                "--no-update",
                url
            ]
        },
        {
            "name": "Метод 4: Только Android клиент",
            "cmd": [
                ytdlp,
                "--no-check-certificates",
                "--user-agent", "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "--extractor-args", "youtube:player_client=android",
                "-J",
                "--ignore-errors",
                "--no-update",
                url
            ]
        },
        {
            "name": "Метод 5: iOS клиент",
            "cmd": [
                ytdlp,
                "--no-check-certificates",
                "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "--extractor-args", "youtube:player_client=ios",
                "-J",
                "--ignore-errors",
                "--no-update",
                url
            ]
        },
        {
            "name": "Метод 6: Без cookies, с web клиентом",
            "cmd": [
                ytdlp,
                "--no-check-certificates",
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--extractor-args", "youtube:player_client=web",
                "-J",
                "--ignore-errors",
                "--no-update",
                url
            ]
        }
    ]
    
    # Добавляем cookies к методам, где их нет
    if cookies_exist:
        for method in methods:
            if "--cookies" not in method["cmd"]:
                # Вставляем после ytdlp
                method["cmd"].insert(1, "--cookies")
                method["cmd"].insert(2, "cookies.txt")
    
    success = False
    for method in methods:
        print(f"\n🔄 {method['name']}...")
        try:
            result = subprocess.run(
                method["cmd"], 
                capture_output=True, 
                text=True, 
                encoding="utf-8"
            )
            
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    print("✅ Успешно!")
                    print(f"  Канал: {data.get('channel', data.get('uploader', 'Неизвестно'))}")
                    print(f"  Название: {data.get('title', 'Неизвестно')}")
                    print(f"  Длительность: {data.get('duration', 0)} сек")
                    success = True
                    break
                except json.JSONDecodeError as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
            else:
                if result.stderr:
                    # Показываем только важные сообщения
                    if "ERROR" in result.stderr:
                        print(f"❌ Ошибка: {result.stderr[:200]}")
                    elif "WARNING" in result.stderr:
                        # Пропускаем предупреждения
                        pass
                    else:
                        print(f"⚠️  {result.stderr[:150]}")
        except Exception as e:
            print(f"❌ Исключение: {e}")
    
    if not success:
        print("\n❌ Все методы не сработали")
        print("\n💡 Рекомендации:")
        print("  1. Обновите yt-dlp: pip install --upgrade yt-dlp")
        print("  2. Проверьте интернет-соединение")
        print("  3. Экспортируйте свежие cookies из браузера")
        print("  4. Попробуйте использовать VPN")
        print("  5. Проверьте, что видео доступно для просмотра")
        
        # Пробуем скачать аудио напрямую
        print("\n🔄 Пробуем скачать аудио напрямую...")
        download_cmd = [
            ytdlp,
            "--no-check-certificates",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--extractor-args", "youtube:player_client=web",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "192",
            "-o", "test_audio.%(ext)s",
            "--no-update",
            url
        ]
        
        if cookies_exist:
            download_cmd.insert(1, "--cookies")
            download_cmd.insert(2, "cookies.txt")
        
        print(f"📝 Команда: {' '.join(download_cmd)}")
        result = subprocess.run(download_cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print("✅ Аудио скачано успешно!")
            print(f"stdout: {result.stdout}")
        else:
            print(f"❌ Ошибка скачивания: {result.stderr[:300]}")
    
    return success

if __name__ == "__main__":
    # Проверяем установку yt-dlp
    ytdlp = find_ytdlp()
    print(f"🔍 Поиск yt-dlp: {ytdlp}")
    
    if not os.path.exists(ytdlp) and ytdlp == "yt-dlp":
        print("❌ yt-dlp не найден!")
        print("\nУстановите yt-dlp:")
        print("  pip install yt-dlp")
        sys.exit(1)
    
    print(f"✅ Найден yt-dlp: {ytdlp}")
    print("=" * 60)
    
    # Проверяем, установлен ли модуль yt-dlp для Python
    try:
        import yt_dlp
        print(f"✅ Модуль yt-dlp установлен в Python")
        # Проверяем версию через pip
        try:
            import pkg_resources
            version = pkg_resources.get_distribution("yt-dlp").version
            print(f"   Версия: {version}")
        except:
            pass
    except ImportError:
        print("❌ Модуль yt-dlp не установлен в Python")
        print("   Установите: pip install yt-dlp")
    
    print("=" * 60)
    
    # Проверяем URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
        test_url(url)
    else:
        # Тестируем URL из вашего лога
        url = "https://www.youtube.com/watch?v=xsHNn-TyRCI"
        test_url(url)