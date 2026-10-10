#!/usr/bin/env python3
# =============================================================================
# Скрипт для расстановки знаков препинания и заглавных букв в текстовых файлах
# 
# Описание:
#   Обрабатывает все .txt файлы в текущей директории (исключая venv, .git и др.),
#   добавляет знаки препинания, заглавные буквы и сохраняет результат.
#
# Использование:
#   python punctuate_texts.py [ОПЦИИ]
#
# Опции:
#   -o, --output DIR     Сохранять результаты в указанную папку (по умолчанию: текущая)
#   -s, --suffix SUFFIX  Суффикс для выходных файлов (по умолчанию: "_punctuated")
#   --overwrite          Перезаписывать исходные файлы (вместо создания новых)
#   -e, --ext EXT        Расширение файлов для обработки (по умолчанию: .txt)
#   --no-recursive       Не обрабатывать подпапки рекурсивно
#   -m, --model MODEL    Модель punctuators (по умолчанию: pcs_47lang)
#   --ignore-dirs DIRS   Дополнительные папки для игнорирования (через запятую)
#   --ignore-files FILES Дополнительные файлы для игнорирования (через запятую)
#   -h, --help           Показать справку
#
# Примеры:
#   python punctuate_texts.py                        # Обработать все .txt, игнорируя venv/.git
#   python punctuate_texts.py --ignore-dirs "venv,env,node_modules"
#   python punctuate_texts.py --ignore-files "README.txt,LICENSE.txt"
# =============================================================================

import os
import sys
import argparse
from pathlib import Path
from punctuators.models import PunctCapSegModelONNX

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
    'logs', 'temp', 'tmp', 'cache'
}

# Файлы, которые всегда игнорируем
DEFAULT_IGNORE_FILES = {
    'README.txt', 'README.md', 'LICENSE.txt', 'LICENSE.md',
    '.gitignore', '.env', '.gitattributes',
    'requirements.txt', 'setup.py', 'Makefile',
    'Dockerfile', 'docker-compose.yml'
}

# Расширения файлов для игнорирования (кроме основного расширения)
DEFAULT_IGNORE_EXTENSIONS = {
    '.exe', '.dll', '.so', '.dylib', '.bin',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
    '.mp3', '.mp4', '.avi', '.mov', '.mkv',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
}

# Модель по умолчанию
DEFAULT_MODEL = 'pcs_47lang'

# Суффикс для выходных файлов по умолчанию
DEFAULT_SUFFIX = '_punctuated'

# =============================================================================

# Цвета для вывода (опционально)
try:
    from colorama import init, Fore, Style
    init()
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    BLUE = Fore.BLUE
    RESET = Style.RESET_ALL
except ImportError:
    GREEN = YELLOW = RED = BLUE = RESET = ''

def print_info(msg):
    print(f"{BLUE}[INFO]{RESET} {msg}")

def print_success(msg):
    print(f"{GREEN}[OK]{RESET} {msg}")

def print_warning(msg):
    print(f"{YELLOW}[WARN]{RESET} {msg}")

def print_error(msg):
    print(f"{RED}[ERROR]{RESET} {msg}")

def load_model(model_name="pcs_47lang"):
    """
    Загрузка модели punctuators
    
    Args:
        model_name: имя модели ('pcs_47lang' для русского/многоязычной)
    
    Returns:
        модель или None при ошибке
    """
    print_info(f"Загрузка модели '{model_name}'...")
    try:
        model = PunctCapSegModelONNX.from_pretrained(model_name)
        print_success(f"Модель загружена")
        return model
    except Exception as e:
        print_error(f"Ошибка загрузки модели: {e}")
        print_info("Убедитесь, что установлен пакет: pip install punctuators")
        return None

def punctuate_text(model, text):
    """
    Добавляет знаки препинания и заглавные буквы в текст
    
    Args:
        model: загруженная модель punctuators
        text: исходный текст
    
    Returns:
        отформатированный текст
    """
    if not text or not text.strip():
        return text
    
    try:
        # Модель ожидает список строк
        results = model.infer([text])
        if results and len(results) > 0:
            # Склеиваем предложения обратно
            formatted = ' '.join(results[0])
            return formatted
        return text
    except Exception as e:
        print_warning(f"Ошибка обработки текста: {e}")
        return text

def should_ignore_path(path, ignore_dirs, ignore_files, ignore_extensions):
    """
    Проверяет, нужно ли игнорировать путь
    
    Args:
        path: путь для проверки
        ignore_dirs: набор игнорируемых директорий
        ignore_files: набор игнорируемых файлов
        ignore_extensions: набор игнорируемых расширений
    
    Returns:
        True если нужно игнорировать
    """
    # Проверяем директории
    parts = path.parts
    for part in parts:
        if part in ignore_dirs:
            return True
    
    # Проверяем файлы
    if path.name in ignore_files:
        return True
    
    # Проверяем расширения
    if path.suffix.lower() in ignore_extensions:
        return True
    
    return False

def find_text_files(directory, extension='.txt', recursive=True, 
                    ignore_dirs=None, ignore_files=None, ignore_extensions=None):
    """
    Находит все текстовые файлы в директории, исключая служебные папки и файлы
    
    Args:
        directory: директория для поиска
        extension: расширение файлов
        recursive: искать в подпапках
        ignore_dirs: множество игнорируемых директорий
        ignore_files: множество игнорируемых файлов
        ignore_extensions: множество игнорируемых расширений
    
    Returns:
        список путей к файлам
    """
    directory = Path(directory)
    if not directory.exists():
        print_error(f"Директория не найдена: {directory}")
        return []
    
    files = []
    
    if recursive:
        # Рекурсивный обход с проверкой
        for root, dirs, filenames in os.walk(directory):
            root_path = Path(root)
            
            # Фильтруем директории для обхода (удаляем игнорируемые)
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            # Проверяем файлы
            for filename in filenames:
                file_path = root_path / filename
                
                # Пропускаем игнорируемые файлы и расширения
                if should_ignore_path(file_path, ignore_dirs, ignore_files, ignore_extensions):
                    continue
                
                if filename.endswith(extension):
                    files.append(file_path)
    else:
        # Только текущая директория
        for item in directory.iterdir():
            if item.is_file() and item.suffix == extension:
                # Проверяем, не игнорируется ли файл
                if should_ignore_path(item, ignore_dirs, ignore_files, ignore_extensions):
                    continue
                files.append(item)
    
    return files

def process_file(model, input_path, output_path):
    """
    Обрабатывает один файл
    
    Args:
        model: загруженная модель
        input_path: путь к исходному файлу
        output_path: путь для сохранения результата
    
    Returns:
        bool: True если успешно
    """
    try:
        # Читаем исходный файл
        with open(input_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
        
        if not original_text.strip():
            print_warning(f"Файл пуст: {input_path.name}")
            return False
        
        # Форматируем текст
        print_info(f"Обработка: {input_path}")
        formatted_text = punctuate_text(model, original_text)
        
        # Создаем директорию для выходного файла если нужно
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем результат
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(formatted_text)
        
        # Показываем пример изменений
        if original_text.strip() != formatted_text.strip():
            print_success(f"Сохранено: {output_path}")
            # Показываем первые 100 символов изменений
            orig_preview = original_text[:80].replace('\n', ' ')
            form_preview = formatted_text[:80].replace('\n', ' ')
            if len(original_text) > 0:
                print(f"  Было: {orig_preview}...")
                print(f"  Стало: {form_preview}...")
        else:
            print_warning(f"Текст не изменился: {input_path.name}")
        
        return True
        
    except Exception as e:
        print_error(f"Ошибка обработки {input_path.name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Расстановка знаков препинания и заглавных букв в текстовых файлах',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s                        # Обработать все .txt, игнорируя venv, .git и др.
  %(prog)s --output formatted     # Сохранить в папку formatted
  %(prog)s --suffix ".fixed"      # Использовать суффикс .fixed
  %(prog)s --overwrite            # Перезаписать исходные файлы
  %(prog)s --ignore-dirs "venv,env,data"  # Добавить папки для игнорирования
  %(prog)s --ignore-files "README.md,LICENSE"  # Игнорировать конкретные файлы
        """
    )
    
    parser.add_argument('-o', '--output', 
                       default='.',
                       help='Директория для сохранения результатов (по умолчанию: текущая)')
    
    parser.add_argument('-s', '--suffix', 
                       default=DEFAULT_SUFFIX,
                       help=f'Суффикс для выходных файлов (по умолчанию: "{DEFAULT_SUFFIX}")')
    
    parser.add_argument('--overwrite', 
                       action='store_true',
                       help='Перезаписывать исходные файлы (вместо создания новых)')
    
    parser.add_argument('-e', '--ext', 
                       default='.txt',
                       help='Расширение файлов для обработки (по умолчанию: .txt)')
    
    parser.add_argument('--no-recursive', 
                       action='store_true',
                       help='Не обрабатывать подпапки рекурсивно')
    
    parser.add_argument('-m', '--model', 
                       default=DEFAULT_MODEL,
                       help=f'Модель punctuators (по умолчанию: {DEFAULT_MODEL})')
    
    parser.add_argument('-d', '--directory',
                       default='.',
                       help='Директория для поиска файлов (по умолчанию: текущая)')
    
    parser.add_argument('--ignore-dirs',
                       default='',
                       help='Дополнительные папки для игнорирования (через запятую)')
    
    parser.add_argument('--ignore-files',
                       default='',
                       help='Дополнительные файлы для игнорирования (через запятую)')
    
    args = parser.parse_args()
    
    # Формируем список игнорируемых директорий
    ignore_dirs = DEFAULT_IGNORE_DIRS.copy()
    if args.ignore_dirs:
        additional = [d.strip() for d in args.ignore_dirs.split(',') if d.strip()]
        ignore_dirs.update(additional)
    
    # Формируем список игнорируемых файлов
    ignore_files = DEFAULT_IGNORE_FILES.copy()
    if args.ignore_files:
        additional = [f.strip() for f in args.ignore_files.split(',') if f.strip()]
        ignore_files.update(additional)
    
    # Игнорируемые расширения (всегда)
    ignore_extensions = DEFAULT_IGNORE_EXTENSIONS.copy()
    
    print_info(f"Игнорируемые папки: {', '.join(sorted(ignore_dirs))}")
    print_info(f"Игнорируемые файлы: {', '.join(sorted(ignore_files))}")
    print_info(f"Игнорируемые расширения: {', '.join(sorted(ignore_extensions))}")
    
    # Проверяем расширение
    if not args.ext.startswith('.'):
        args.ext = '.' + args.ext
    
    # Проверяем существование директории
    search_dir = Path(args.directory).resolve()
    if not search_dir.exists():
        print_error(f"Директория не найдена: {search_dir}")
        sys.exit(1)
    
    print_info(f"Поиск в: {search_dir}")
    print_info(f"Расширение: {args.ext}")
    
    # Находим все текстовые файлы
    files = find_text_files(
        search_dir, 
        args.ext, 
        not args.no_recursive,
        ignore_dirs,
        ignore_files,
        ignore_extensions
    )
    
    if not files:
        print_warning(f"Файлы с расширением '{args.ext}' не найдены")
        sys.exit(0)
    
    print_info(f"Найдено файлов: {len(files)}")
    
    # Показываем список файлов
    if len(files) <= 10:
        for f in files:
            print(f"  - {f.relative_to(search_dir)}")
    else:
        for f in files[:5]:
            print(f"  - {f.relative_to(search_dir)}")
        print(f"  ... и {len(files) - 5} других")
    
    # Загружаем модель
    model = load_model(args.model)
    if model is None:
        sys.exit(1)
    
    # Обрабатываем файлы
    print("\n" + "="*60)
    print_info("Начинаем обработку...")
    print("="*60)
    
    success_count = 0
    error_count = 0
    
    for input_file in files:
        # Определяем выходной файл
        if args.overwrite:
            output_file = input_file
        else:
            # Добавляем суффикс перед расширением
            output_file = input_file.parent / f"{input_file.stem}{args.suffix}{args.ext}"
        
        # Если выходная папка указана и не совпадает с текущей
        if args.output != '.' and not args.overwrite:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            # Сохраняем структуру подпапок
            relative_path = input_file.relative_to(search_dir)
            output_file = output_dir / relative_path.parent / f"{relative_path.stem}{args.suffix}{args.ext}"
        
        # Обрабатываем файл
        if process_file(model, input_file, output_file):
            success_count += 1
        else:
            error_count += 1
    
    # Выводим статистику
    print("\n" + "="*60)
    print_info("СТАТИСТИКА:")
    print(f"  ✅ Успешно: {success_count}")
    print(f"  ❌ Ошибок: {error_count}")
    print("="*60)
    
    if success_count > 0:
        print_success("Готово!")

if __name__ == "__main__":
    main()