# TODO — youtube-playlist-downloader

Идеи и задачи на будущее.

---

## Архитектура: папка для каждого видео

**Идея:** вместо «плоской» структуры (все файлы рядом с длинными
суффиксами) — **папка на каждое видео**:

    data/Video_Youtube/
    ├── Война в Югославии/
    │   ├── audio.mp3
    │   ├── transcript.txt
    │   ├── punctuated.txt
    │   └── summary.md
    ├── Экономическое чудо Китая/
    │   ├── audio.mp3
    │   └── ...

**Плюсы:**
- Логично: всё по видео в одном месте.
- Короткие имена (`audio.mp3`, `summary.md`).
- Нет дублей (`_summary.md` + `_punctuated_summary.md`).
- Легко удалить: `rm -rf "Война в Югославии/"`.

**Минусы / риски:**
- Переработка **всех 4 скриптов** (`ytdl`, `transcribe`, `punctuate`,
  `summarize`) — каждый пишет в плоскую структуру.
- Миграция существующих файлов.
- `skip_suffix` → провepка наличия файла в папке.

**Оценка:** ~2-4 часа. **Риск:** средний. **Приоритет:** 🟡 средний.

**План (отдельная сессия):**
1. Пилот — на **одном** видео (или новом пайплайне).
2. Сначала `ytdl.py` — писать `audio.mp3` в папку.
3. Потом `transcribe.py` → `transcript.txt` рядом.
4. Затем `punctuate.py` → `punctuated.txt`.
5. `summarize.py` → `summary.md`.
6. Миграция существующих файлов (скриптом).

---

## Мелкие фиксы

- [ ] **Удалить дубли `_summary.md`** (старые артефакты до E9).
      `find data/Video_Youtube -name "*_summary.md" ! -name "*_punctuated_summary.md"`
- [ ] **`[WARN]` → `[INFO]`** в `summarize.py` для «Пропускаем (уже есть)».
      Семантически точнее.
- [ ] **`basename`** — обрезать `_punctuated` из имени? Сейчас
      `_punctuated_summary.md`, а комментарий в коде говорит `_summary.md`.

---

## Сделано

- [x] **`ytdl.py`** — `download_single_video` возвращает тройку
      `(success, stats_str, final_path)` (E12, 2026-10-11).
- [x] **`summarize.py`** — пропуск существующих `_punctuated_summary.md`
      (экономия DeepSeek). 2026-10-11.
- [x] **`skip_suffix`** в `punctuate.py` — пропуск `_punctuated.txt`.
