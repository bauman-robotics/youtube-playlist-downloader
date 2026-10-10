#!/usr/bin/env python3
# =============================================================================
# summarize.py — суммаризация текстов через DeepSeek API
#
# Читает <basename>_punctuated.txt из указанной папки, отправляет содержимое
# в DeepSeek с промптом из prompts.yaml и сохраняет <basename>_summary.md
# рядом с исходным .txt файлом.
#
# Использование:
#   python src/summarize.py -d ./data/transcripts
#   python src/summarize.py -d ./data/transcripts --prompt summary
#   python src/summarize.py -d ./data --prompt short --project-root /path/to/project
# =============================================================================

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# =============================================================================
# НАСТРОЙКИ
# =============================================================================

DEFAULT_PROMPT_NAME = "summary"
DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
SUFFIX_INPUT = "_punctuated.txt"
SUFFIX_OUTPUT = "_summary.md"
PLACEHOLDER_KEY_PREFIX = "sk-your-"


def print_info(msg):
    print(f"[INFO] {msg}")


def print_success(msg):
    print(f"[OK] {msg}")


def print_warning(msg):
    print(f"[WARN] {msg}")


def print_error(msg):
    print(f"[ERROR] {msg}")


def default_project_root():
    """2 уровня вверх от __file__ (src/summarize.py -> корень проекта)."""
    return Path(__file__).resolve().parent.parent


# =============================================================================
# ЗАГРУЗКА ПРОМПТОВ
# =============================================================================

def load_prompts(project_root):
    """Читает prompts.yaml из корня проекта."""
    path = Path(project_root) / "prompts.yaml"
    if not path.exists():
        print_error("не найден prompts.yaml")
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print_error("Для чтения prompts.yaml нужен PyYAML. Установите: pip install pyyaml")
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print_error(f"Не удалось прочитать prompts.yaml: {e}")
        sys.exit(1)

    if not isinstance(data, dict):
        print_error("prompts.yaml должен содержать словарь промптов (name: ...)")
        sys.exit(1)

    # Поддержка вложенного формата {prompts: {name: {...}}}
    if "prompts" in data and isinstance(data["prompts"], dict):
        data = data["prompts"]

    return data


def get_prompt(prompts, name):
    """Извлекает промпт по имени. Возвращает (model, system, user_prompt)."""
    if name not in prompts:
        available = ", ".join(sorted(prompts.keys())) or "(нет)"
        print_error(f"Промпт '{name}' не найден в prompts.yaml. Доступные: {available}")
        sys.exit(1)

    entry = prompts[name]

    # Промпт может быть просто строкой.
    if isinstance(entry, str):
        return DEFAULT_MODEL, None, entry

    if not isinstance(entry, dict):
        print_error(f"Промпт '{name}' имеет неверный формат (ожидается строка или словарь)")
        sys.exit(1)

    model = entry.get("model", DEFAULT_MODEL)
    system = entry.get("system") or entry.get("system_prompt")
    user_prompt = (entry.get("prompt") or entry.get("template")
                   or entry.get("text") or entry.get("user"))

    if not user_prompt:
        print_error(f"В промпте '{name}' не найдено поле с текстом (prompt/template/text)")
        sys.exit(1)

    return model, system, user_prompt


# =============================================================================
# API-КЛЮЧ
# =============================================================================

def load_api_key(project_root):
    """secret_conf.yaml -> env DEEPSEEK_API_KEY -> ошибка."""
    secret_path = Path(project_root) / "secret_conf.yaml"

    if secret_path.exists():
        try:
            import yaml
        except ImportError:
            print_error("Для чтения secret_conf.yaml нужен PyYAML. Установите: pip install pyyaml")
            sys.exit(1)

        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                secret = yaml.safe_load(f) or {}
        except Exception as e:
            print_error(f"Не удалось прочитать secret_conf.yaml: {e}")
            sys.exit(1)

        if isinstance(secret, dict):
            key = (secret.get("deepseek_api_key")
                   or secret.get("api_key")
                   or secret.get("DEEPSEEK_API_KEY"))
            if key:
                key = str(key).strip()
                if key.startswith(PLACEHOLDER_KEY_PREFIX):
                    print_error("заполни реальный ключ в secret_conf.yaml")
                    sys.exit(1)
                return key

    env_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env_key and not env_key.startswith(PLACEHOLDER_KEY_PREFIX):
        return env_key

    print_error(
        "Не найден DEEPSEEK_API_KEY. Укажите ключ в secret_conf.yaml "
        "(deepseek_api_key) или задайте переменную окружения DEEPSEEK_API_KEY."
    )
    sys.exit(1)


# =============================================================================
# ВЫЗОВ DEEPSEEK
# =============================================================================

def call_deepseek(api_key, model, system, user_prompt, text, timeout=180):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    rendered = user_prompt
    if "{text}" in rendered:
        rendered = rendered.replace("{text}", text)
        messages.append({"role": "user", "content": rendered})
    else:
        messages.append({"role": "user", "content": rendered})
        messages.append({"role": "user", "content": text})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print_error(f"DeepSeek API вернул ошибку {e.code}: {detail}")
        return None
    except urllib.error.URLError as e:
        print_error(f"Ошибка соединения с DeepSeek API: {e.reason}")
        return None
    except Exception as e:
        print_error(f"Ошибка запроса к DeepSeek API: {e}")
        return None

    try:
        parsed = json.loads(body)
        return parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        print_error(f"Неожиданный ответ от DeepSeek API: {e}")
        return None


# =============================================================================
# ОБРАБОТКА ФАЙЛОВ
# =============================================================================

def find_input_files(directory):
    directory = Path(directory)
    if not directory.exists():
        print_error(f"Директория не найдена: {directory}")
        return []
    if not directory.is_dir():
        print_error(f"Не директория: {directory}")
        return []
    return sorted(directory.rglob(f"*{SUFFIX_INPUT}"))


def summarize_file(path, api_key, model, system, user_prompt):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        print_error(f"Не удалось прочитать {path}: {e}")
        return False

    if not text.strip():
        print_warning(f"Файл пуст: {path.name}")
        return False

    print_info(f"Отправка в DeepSeek: {path.name} (модель: {model})")
    summary = call_deepseek(api_key, model, system, user_prompt, text)
    if summary is None:
        return False

    basename = path.name[:-len(".txt")]
    output_path = path.with_name(f"{basename}{SUFFIX_OUTPUT}")
    try:
        output_path.write_text(summary, encoding="utf-8")
    except Exception as e:
        print_error(f"Не удалось сохранить {output_path}: {e}")
        return False

    print_success(f"Сохранено: {output_path}")
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Суммаризация _punctuated.txt файлов через DeepSeek API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-d", "--dir",
        required=True,
        help="Папка с *_punctuated.txt файлами",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT_NAME,
        help=f"Имя промпта из prompts.yaml (по умолчанию: {DEFAULT_PROMPT_NAME})",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Корень проекта (по умолчанию: 2 уровня вверх от __file__)",
    )

    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else default_project_root()

    prompts = load_prompts(project_root)
    model, system, user_prompt = get_prompt(prompts, args.prompt)
    api_key = load_api_key(project_root)

    files = find_input_files(args.dir)
    if not files:
        print_warning(f"Не найдено *{SUFFIX_INPUT} файлов в {args.dir}")
        return 0

    ok = 0
    for path in files:
        if summarize_file(path, api_key, model, system, user_prompt):
            ok += 1

    print_info(f"Обработано: {ok}/{len(files)}")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
