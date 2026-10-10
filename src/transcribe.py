#!/usr/bin/env python3
"""
Batch audio transcription using Vosk
Processes all audio files in a folder, converts them to WAV (16kHz, mono),
and saves transcription to .txt files with the same name.
"""

import os
import sys
import json
import wave
import subprocess
import argparse
from pathlib import Path
from vosk import Model, KaldiRecognizer

# =============================================================================
# НАСТРОЙКИ (можно изменять)
# =============================================================================

# Папки, которые всегда игнорируем при поиске
DEFAULT_IGNORE_DIRS = {
    'venv', 'env', '.venv', 'virtualenv',
    '__pycache__', '.git', '.svn', '.hg',
    '.idea', '.vscode', '.pytest_cache',
    'node_modules', 'dist', 'build', '.tox',
    '.mypy_cache', '.ruff_cache', '.coverage',
    'logs', 'temp', 'tmp', 'cache',
    'output', 'results', 'transcripts',  # часто используемые папки для результатов
    'backup', 'archive', 'old'
}

# Файлы, которые всегда игнорируем
DEFAULT_IGNORE_FILES = {
    'README.txt', 'README.md', 'LICENSE.txt', 'LICENSE.md',
    '.gitignore', '.env', '.gitattributes',
    'requirements.txt', 'setup.py', 'Makefile',
    'Dockerfile', 'docker-compose.yml',
    '.DS_Store', 'Thumbs.db',  # системные файлы
    'desktop.ini'  # системные файлы Windows
}

# Расширения файлов для игнорирования (кроме аудио)
DEFAULT_IGNORE_EXTENSIONS = {
    '.exe', '.dll', '.so', '.dylib', '.bin',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
    '.mp4', '.avi', '.mov', '.mkv',  # видео (не аудио)
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.log', '.csv', '.json', '.xml', '.html', '.css', '.js',
    '.py', '.java', '.cpp', '.c', '.h'
}

# Расширения аудиофайлов, которые поддерживаются
SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus'}

# =============================================================================

class AudioTranscriber:
    def __init__(self, model_path, sample_rate=16000):
        """
        Инициализация транскрибатора
        
        Args:
            model_path: путь к модели Vosk
            sample_rate: частота дискретизации (16000 для Vosk)
        """
        self.sample_rate = sample_rate
        self.model = Model(model_path)
        self.ignore_dirs = DEFAULT_IGNORE_DIRS.copy()
        self.ignore_files = DEFAULT_IGNORE_FILES.copy()
        self.ignore_extensions = DEFAULT_IGNORE_EXTENSIONS.copy()
        
    def add_ignore_patterns(self, ignore_dirs=None, ignore_files=None):
        """
        Добавляет паттерны для игнорирования
        
        Args:
            ignore_dirs: список или множество игнорируемых папок
            ignore_files: список или множество игнорируемых файлов
        """
        if ignore_dirs:
            self.ignore_dirs.update(ignore_dirs)
        if ignore_files:
            self.ignore_files.update(ignore_files)
    
    def should_ignore_path(self, path):
        """
        Проверяет, нужно ли игнорировать путь
        
        Args:
            path: путь для проверки
            
        Returns:
            True если нужно игнорировать
        """
        # Проверяем директории
        parts = path.parts
        for part in parts:
            if part in self.ignore_dirs:
                return True
        
        # Проверяем файлы
        if path.name in self.ignore_files:
            return True
        
        # Проверяем расширения
        if path.suffix.lower() in self.ignore_extensions:
            return True
        
        return False
        
    def convert_to_wav(self, input_path, output_path):
        """
        Конвертирует аудиофайл в WAV (16kHz, моно, 16-bit)
        
        Args:
            input_path: путь к исходному файлу
            output_path: путь для сохранения WAV файла
            
        Returns:
            bool: True если успешно, False если ошибка
        """
        try:
            command = [
                'ffmpeg', '-i', str(input_path),
                '-acodec', 'pcm_s16le',
                '-ac', '1',
                '-ar', str(self.sample_rate),
                '-y',  # перезаписывать существующий файл
                str(output_path)
            ]
            
            # Запускаем ffmpeg, скрывая вывод
            subprocess.run(command, check=True, 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Ошибка конвертации: {e}")
            return False
        except FileNotFoundError:
            print("  ❌ FFmpeg не установлен. Установите: sudo apt install ffmpeg")
            return False
    
    def transcribe_file(self, audio_path, text_path=None):
        """
        Транскрибирует один аудиофайл и сохраняет результат
        
        Args:
            audio_path: путь к аудиофайлу (mp3, wav и т.д.)
            text_path: путь для сохранения текста (если None, заменит расширение на .txt)
            
        Returns:
            str: распознанный текст или None при ошибке
        """
        # Определяем путь для сохранения текста
        if text_path is None:
            text_path = Path(audio_path).with_suffix('.txt')
        
        print(f"\n📁 Обработка: {Path(audio_path).name}")
        
        # Если файл не WAV - конвертируем во временный файл
        temp_wav = None
        if Path(audio_path).suffix.lower() != '.wav':
            temp_wav = Path(audio_path).with_suffix('.temp.wav')
            print(f"  🔄 Конвертация в WAV...")
            if not self.convert_to_wav(audio_path, temp_wav):
                return None
            process_path = temp_wav
        else:
            process_path = audio_path
        
        try:
            # Открываем WAV файл
            wf = wave.open(str(process_path), 'rb')
            
            # Проверяем параметры файла
            if wf.getframerate() != self.sample_rate:
                print(f"  ⚠️ Частота {wf.getframerate()} Гц, конвертируем в {self.sample_rate} Гц...")
                wf.close()
                # Переконвертируем с правильной частотой
                temp_wav2 = Path(audio_path).with_suffix('.temp2.wav')
                self.convert_to_wav(audio_path, temp_wav2)
                process_path = temp_wav2
                wf = wave.open(str(process_path), 'rb')
            
            if wf.getnchannels() != 1:
                print(f"  ⚠️ Файл имеет {wf.getnchannels()} канала, конвертируем в моно...")
                wf.close()
                temp_wav2 = Path(audio_path).with_suffix('.temp2.wav')
                self.convert_to_wav(audio_path, temp_wav2)
                process_path = temp_wav2
                wf = wave.open(str(process_path), 'rb')
            
            # Создаем распознаватель
            rec = KaldiRecognizer(self.model, wf.getframerate())
            rec.SetWords(True)  # Включаем вывод слов с таймкодами
            
            # Распознаем
            print(f"  🎤 Распознавание...")
            recognized_text = []
            
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if text := result.get('text', '').strip():
                        recognized_text.append(text)
                        # Выводим прогресс (каждую фразу)
                        print(f"    > {text}")
            
            # Получаем последнюю часть
            final_result = json.loads(rec.FinalResult())
            if text := final_result.get('text', '').strip():
                recognized_text.append(text)
                print(f"    > {text}")
            
            wf.close()
            
            # Сохраняем результат
            full_text = ' '.join(recognized_text)
            if full_text:
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                print(f"  ✅ Сохранено: {text_path}")
                return full_text
            else:
                print(f"  ⚠️ Текст не распознан")
                return None
                
        except Exception as e:
            print(f"  ❌ Ошибка при распознавании: {e}")
            return None
        finally:
            # Удаляем временные файлы
            if temp_wav and temp_wav.exists():
                temp_wav.unlink()
            # Удаляем второй временный файл если был
            temp_file = Path(audio_path).with_suffix('.temp2.wav')
            if temp_file.exists():
                temp_file.unlink()
    
    def transcribe_folder(self, folder_path, recursive=True, extensions=None, force=False):
        """
        Транскрибирует все аудиофайлы в папке
        
        Args:
            folder_path: путь к папке
            recursive: обрабатывать подпапки рекурсивно
            extensions: список расширений (если None - все поддерживаемые)
            force: перезаписывать существующие файлы
            
        Returns:
            dict: статистика обработки
        """
        folder = Path(folder_path)
        if not folder.exists():
            print(f"❌ Папка не найдена: {folder_path}")
            return None
        
        # Расширения для поиска
        if extensions is None:
            extensions = SUPPORTED_EXTENSIONS
        else:
            extensions = set(ext.lower() for ext in extensions)
        
        print(f"\n📋 Игнорируемые папки: {', '.join(sorted(self.ignore_dirs))}")
        print(f"📋 Игнорируемые файлы: {', '.join(sorted(self.ignore_files))}")
        
        # Собираем все аудиофайлы с проверкой игнорирования
        audio_files = []
        if recursive:
            for root, dirs, filenames in os.walk(folder):
                root_path = Path(root)
                
                # Фильтруем директории для обхода (удаляем игнорируемые)
                dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
                
                # Проверяем файлы
                for filename in filenames:
                    file_path = root_path / filename
                    
                    # Проверяем, не игнорируется ли файл
                    if self.should_ignore_path(file_path):
                        continue
                    
                    if file_path.suffix.lower() in extensions:
                        audio_files.append(file_path)
        else:
            # Только текущая директория
            for item in folder.iterdir():
                if item.is_file():
                    # Проверяем, не игнорируется ли файл
                    if self.should_ignore_path(item):
                        continue
                    if item.suffix.lower() in extensions:
                        audio_files.append(item)
        
        if not audio_files:
            print(f"⚠️ Аудиофайлы не найдены в: {folder_path}")
            return None
        
        print(f"\n{'='*60}")
        print(f"📂 Найдено файлов: {len(audio_files)}")
        print(f"{'='*60}")
        
        # Статистика
        stats = {
            'total': len(audio_files),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'files': []
        }
        
        # Обрабатываем каждый файл
        for audio_file in audio_files:
            # Проверяем, существует ли уже текстовый файл
            txt_file = audio_file.with_suffix('.txt')
            if not force and txt_file.exists() and txt_file.stat().st_size > 0:
                print(f"\n⏭️ Пропускаем (уже есть): {audio_file.name}")
                stats['skipped'] += 1
                continue
            
            # Транскрибируем
            result = self.transcribe_file(audio_file)
            
            if result:
                stats['success'] += 1
                stats['files'].append({
                    'audio': str(audio_file),
                    'text': str(txt_file),
                    'content': result[:100] + '...' if len(result) > 100 else result
                })
            else:
                stats['failed'] += 1
        
        # Выводим итоги
        print(f"\n{'='*60}")
        print(f"📊 ИТОГИ:")
        print(f"   ✅ Успешно: {stats['success']}")
        print(f"   ❌ Ошибок: {stats['failed']}")
        print(f"   ⏭️ Пропущено: {stats['skipped']}")
        print(f"   📁 Всего: {stats['total']}")
        print(f"{'='*60}")
        
        return stats

def main():
    parser = argparse.ArgumentParser(
        description='Пакетная транскрибация аудиофайлов с помощью Vosk'
    )
    parser.add_argument('folder', nargs='?', default='.',
                       help='Путь к папке с аудиофайлами (по умолчанию: текущая папка)')
    parser.add_argument('--model', default='vosk-model-small-ru-0.22',
                       help='Путь к модели Vosk (по умолчанию: vosk-model-small-ru-0.22)')
    parser.add_argument('--no-recursive', action='store_true',
                       help='Не обрабатывать подпапки рекурсивно')
    parser.add_argument('--extensions', nargs='+', 
                       default=['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus'],
                       help='Расширения файлов для обработки')
    parser.add_argument('--force', action='store_true',
                       help='Перезаписать существующие .txt файлы')
    parser.add_argument('--ignore-dirs', default='',
                       help='Дополнительные папки для игнорирования (через запятую)')
    parser.add_argument('--ignore-files', default='',
                       help='Дополнительные файлы для игнорирования (через запятую)')
    
    args = parser.parse_args()
    
    # Проверяем наличие модели
    if not os.path.exists(args.model):
        print(f"❌ Модель не найдена: {args.model}")
        print(f"Скачайте модель с https://alphacephei.com/vosk/models")
        print(f"Например: wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip")
        print(f"И распакуйте: unzip vosk-model-small-ru-0.22.zip")
        sys.exit(1)
    
    # Создаем транскрибатор
    print(f"🔧 Загрузка модели Vosk...")
    transcriber = AudioTranscriber(args.model)
    
    # Добавляем дополнительные игнорируемые папки и файлы
    extra_dirs = []
    if args.ignore_dirs:
        extra_dirs = [d.strip() for d in args.ignore_dirs.split(',') if d.strip()]
        transcriber.add_ignore_patterns(ignore_dirs=extra_dirs)
    
    extra_files = []
    if args.ignore_files:
        extra_files = [f.strip() for f in args.ignore_files.split(',') if f.strip()]
        transcriber.add_ignore_patterns(ignore_files=extra_files)
    
    print(f"✅ Модель загружена")
    
    # Запускаем обработку
    stats = transcriber.transcribe_folder(
        args.folder,
        recursive=not args.no_recursive,
        extensions=args.extensions,
        force=args.force
    )
    
    if stats and stats['success'] > 0:
        print(f"\n✨ Готово! Транскрипции сохранены в .txt файлы рядом с аудио.")

if __name__ == "__main__":
    main()