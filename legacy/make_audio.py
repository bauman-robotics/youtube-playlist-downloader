import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}

def process_video_files():
    output_dir = Path("extracted_audio")
    output_dir.mkdir(exist_ok=True)
    
    video_files = [f for f in Path.cwd().iterdir() 
                   if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
    
    if not video_files:
        print("❌ Видеофайлы не найдены")
        return
    
    print(f"\n📹 Найдено файлов: {len(video_files)}\n")
    
    for i, video_file in enumerate(video_files, 1):
        output_file = output_dir / f"{video_file.stem}.mp3"
        
        print(f"[{i}/{len(video_files)}] 🎬 {video_file.name}")
        print(f"     ⏳ Извлечение аудио...", end=" ", flush=True)
        
        cmd = [
            'ffmpeg', '-i', str(video_file), '-vn',
            '-acodec', 'libmp3lame', '-ab', '192k', '-y',
            str(output_file), '-progress', 'pipe:1', '-nostats'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if output_file.exists():
            size = output_file.stat().st_size / (1024 * 1024)
            print(f"✅ {size:.1f} МБ")
        else:
            print("❌ Ошибка")
    
    print(f"\n✅ Готово! Аудио в папке '{output_dir}'")

if __name__ == "__main__":
    process_video_files()