import subprocess
import sys
from pathlib import Path

# Устанавливаем tqdm для прогресс-бара (если не установлен)
try:
    from tqdm import tqdm
except ImportError:
    print("Устанавливаем tqdm для прогресс-бара...")
    subprocess.run([sys.executable, "-m", "pip", "install", "tqdm"], capture_output=True)
    from tqdm import tqdm

# Расширения видеофайлов
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'}

def check_ffmpeg():
    """Проверяет наличие ffmpeg в системе"""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        print("Ошибка: ffmpeg не найден. Установите ffmpeg:")
        print("  - Windows: скачайте с https://ffmpeg.org/")
        print("  - Linux: sudo apt install ffmpeg")
        print("  - Mac: brew install ffmpeg")
        return False

def get_video_duration(video_path):
    """Получает длительность видео в секундах для прогресс-бара"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return None

def process_video_files():
    """Извлекает аудио из всех видеофайлов в текущей папке"""
    
    # Папка для аудиофайлов
    output_dir = Path("extracted_audio")
    output_dir.mkdir(exist_ok=True)
    
    # Получаем все видеофайлы
    current_dir = Path.cwd()
    video_files = [f for f in current_dir.iterdir() 
                   if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
    
    if not video_files:
        print("❌ Видеофайлы не найдены в текущей папке.")
        print(f"Поддерживаемые расширения: {', '.join(VIDEO_EXTENSIONS)}")
        return
    
    print(f"\n📹 Найдено видеофайлов: {len(video_files)}")
    print(f"📁 Аудио будут сохранены в папку: {output_dir}\n")
    
    # Основной прогресс-бар для файлов
    for video_file in tqdm(video_files, desc="Общий прогресс", unit="файл", position=0):
        base_name = video_file.stem
        output_file = output_dir / f"{base_name}.mp3"
        
        # Проверяем, существует ли уже файл
        if output_file.exists():
            tqdm.write(f"⏭️  Пропускаем {video_file.name} (файл уже существует)")
            continue
        
        tqdm.write(f"\n🎬 Обработка: {video_file.name}")
        
        # Получаем длительность для точного прогресс-бара
        duration = get_video_duration(video_file)
        
        # Команда ffmpeg
        cmd = [
            'ffmpeg',
            '-i', str(video_file),
            '-vn',           # Без видео
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-y',
            str(output_file)
        ]
        
        # Запускаем ffmpeg с выводом прогресса
        if duration:
            # Создаём прогресс-бар для текущего файла
            with tqdm(total=duration, desc=f"  Конвертация", unit="сек", 
                     position=1, leave=False, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} сек') as pbar:
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                # Читаем вывод ffmpeg для отслеживания прогресса
                for line in process.stderr:
                    if 'time=' in line:
                        # Извлекаем текущее время
                        time_str = line.split('time=')[1].split()[0]
                        try:
                            if ':' in time_str:
                                # Преобразуем HH:MM:SS.MS в секунды
                                h, m, s = time_str.split(':')
                                current_time = int(h) * 3600 + int(m) * 60 + float(s)
                                pbar.n = current_time
                                pbar.refresh()
                        except:
                            pass
                
                process.wait()
        else:
            # Если не удалось получить длительность, используем простой вариант
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                tqdm.write(f"  ❌ Ошибка при обработке {video_file.name}")
        
        # Проверяем результат
        if output_file.exists():
            file_size = output_file.stat().st_size / (1024 * 1024)
            tqdm.write(f"  ✅ Сохранено: {output_file.name} ({file_size:.2f} МБ)")
        else:
            tqdm.write(f"  ❌ Ошибка: не удалось создать {output_file.name}")
    
    print(f"\n✅ Готово! Все аудиофайлы сохранены в папке '{output_dir}'")

def main():
    print("=" * 50)
    print("🎵 ИЗВЛЕЧЕНИЕ АУДИО ИЗ ВИДЕОФАЙЛОВ")
    print("=" * 50)
    
    if not check_ffmpeg():
        sys.exit(1)
    
    process_video_files()

if __name__ == "__main__":
    main()