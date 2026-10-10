#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gui.py — Tkinter-интерфейс для ytdl.py

Возможности:
- поле для ссылки
- чекбокс "аудио" (маркер [audio])
- спиннер "количество" (маркер [top=N] для каналов)
- кнопки: Запустить, Стоп, Открыть папку
- лог (Text + Scrollbar) и неопределённый Progressbar
- запуск ytdl.py через subprocess.Popen, чтение stdout в отдельном потоке
  с передачей строк через queue и обновлением GUI через after(100)
"""

import os
import platform
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


class YtdlApp(tk.Tk):
    """Графический интерфейс для скачивания через ytdl.py"""

    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader")
        self.geometry("860x620")
        self.minsize(680, 480)

        # --- состояние ---
        self.proc = None
        self.reader_thread = None
        self.queue = queue.Queue()
        self.script_dir = Path(__file__).resolve().parent
        self.ytdl_script = self.script_dir / "ytdl.py"
        self.input_file = self.script_dir / "gui_input.txt"
        self.download_dir = self._read_download_root()

        # --- тёмная тема ---
        self._setup_dark_theme()

        # --- построение интерфейса ---
        self._build_ui()

        # периодический опрос очереди
        self.after(100, self._poll_queue)

        # корректное закрытие
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Тёмная тема
    # ------------------------------------------------------------------
    def _setup_dark_theme(self):
        """Настраивает тёмную тему для ttk-виджетов"""
        bg = "#1e1e1e"
        fg = "#e0e0e0"
        field_bg = "#2d2d2d"
        button_bg = "#3c3c3c"
        select_bg = "#4a6fa5"

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(bg=bg)

        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure(
            "TButton",
            background=button_bg,
            foreground=fg,
        )
        style.map(
            "TButton",
            background=[("active", select_bg)],
            foreground=[("active", fg)],
        )
        style.configure(
            "TEntry",
            fieldbackground=field_bg,
            foreground=fg,
            insertcolor=fg,
        )
        style.configure(
            "TCheckbutton",
            background=bg,
            foreground=fg,
        )
        style.map(
            "TCheckbutton",
            background=[("active", bg)],
            foreground=[("active", fg)],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=field_bg,
            foreground=fg,
            background=button_bg,
            arrowcolor=fg,
        )
        style.map(
            "TSpinbox",
            fieldbackground=[("active", field_bg)],
            foreground=[("active", fg)],
        )
        style.configure("TScrollbar", background=button_bg, troughcolor=bg)

    # ------------------------------------------------------------------
    # Инициализация интерфейса
    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 6, "pady": 4}

        # ===== Верхняя панель: ссылка =====
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Ссылка:").pack(side="left")

        url_frame = ttk.Frame(top)
        url_frame.pack(side="left", fill="x", expand=True, padx=6)

        self.url_text = tk.Text(
            url_frame,
            wrap="word",
            height=6,
            bg="#1e1e1e",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
        )
        self.url_text.pack(side="left", fill="both", expand=True)

        url_scroll = ttk.Scrollbar(
            url_frame, orient="vertical", command=self.url_text.yview
        )
        url_scroll.pack(side="right", fill="y")
        self.url_text.configure(yscrollcommand=url_scroll.set)
        self._add_context_menu(self.url_text)

        # ===== Панель опций: аудио + количество =====
        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)

        self.audio_var = tk.BooleanVar(value=False)
        self.audio_check = ttk.Checkbutton(
            opts, text="аудио (MP3)", variable=self.audio_var
        )
        self.audio_check.pack(side="left")

        ttk.Label(opts, text="количество:").pack(side="left", padx=(20, 4))
        self.count_var = tk.IntVar(value=0)
        self.count_spin = ttk.Spinbox(
            opts, from_=0, to=9999, width=6, textvariable=self.count_var
        )
        self.count_spin.pack(side="left")
        ttk.Label(opts, text="(0 = без ограничения, [top=N] для канала)").pack(
            side="left", padx=6
        )

        # ===== Панель кнопок =====
        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)

        self.start_btn = ttk.Button(btns, text="Запустить", command=self._start)
        self.start_btn.pack(side="left")

        self.stop_btn = ttk.Button(btns, text="Стоп", command=self._stop)
        self.stop_btn.pack(side="left", padx=6)

        self.folder_btn = ttk.Button(
            btns, text="Открыть папку", command=self._open_folder
        )
        self.folder_btn.pack(side="left", padx=6)

        # ===== Лог: Text + Scrollbar =====
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            height=20,
            bg="#1e1e1e",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self._add_context_menu(self.log_text)

        # стартовое сообщение
        self._append_log(f"ytdl.py: {self.ytdl_script}\n")
        self._append_log(f"Папка загрузок: {self.download_dir}\n")

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------
    def _read_download_root(self):
        """Пытается прочитать download_root из config.yaml"""
        default = "/run/media/ypc/ADATA_1TB/Video_Youtube"
        cfg = self.script_dir / "config.yaml"
        try:
            for line in cfg.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("download_root:"):
                    value = line.split(":", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        except Exception:
            pass
        return default

    def _append_log(self, text):
        """Добавляет текст в лог и прокручивает вниз"""
        self.log_text.insert("end", text)
        self.log_text.see("end")

    def _add_context_menu(self, widget):
        """Добавляет контекстное меню (правый клик) к виджету

        Пункты: Копировать, Вставить, Выделить всё.
        """
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(
            label="Копировать",
            command=lambda: widget.event_generate("<<Copy>>"),
        )
        menu.add_command(
            label="Вставить",
            command=lambda: widget.event_generate("<<Paste>>"),
        )
        menu.add_command(
            label="Выделить всё",
            command=lambda: widget.tag_add("sel", "1.0", "end"),
        )

        def _show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", _show_menu)

    # ------------------------------------------------------------------
    # Запуск / остановка процесса
    # ------------------------------------------------------------------
    def _build_input_file(self, audio, count):
        """Берёт текст из поля ссылок, разбивает по строкам и пишет в файл"""
        raw = self.url_text.get("1.0", "end")
        urls = [line.strip() for line in raw.splitlines() if line.strip()]

        markers = []
        if audio:
            markers.append("[audio]")
        if count and count > 0:
            markers.append(f"[top={count}]")

        out_lines = [" ".join([url] + markers) for url in urls]
        self.input_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        return self.input_file

    def _start(self):
        """Запускает ytdl.py в отдельном процессе"""
        if self.proc is not None and self.proc.poll() is None:
            messagebox.showinfo("Внимание", "Процесс уже запущен")
            return

        raw = self.url_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("Внимание", "Введите ссылку")
            return

        if not self.ytdl_script.exists():
            messagebox.showerror("Ошибка", f"Файл не найден:\n{self.ytdl_script}")
            return

        audio = bool(self.audio_var.get())
        try:
            count = int(self.count_var.get())
        except Exception:
            count = 0

        try:
            self._build_input_file(audio, count)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось записать входной файл:\n{exc}")
            return

        # Базовая команда — запуск ytdl.py текущим интерпретатором
        cmd = [sys.executable, "-u", "ytdl.py"]
        cmd += ["--input", str(self.input_file)]

        self._append_log("\n" + "-" * 60 + "\n")
        self._append_log("$ " + " ".join(cmd) + "\n")

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(self.script_dir),
            )
        except Exception as exc:
            self.proc = None
            self._append_log(f"[GUI] Ошибка запуска: {exc}\n")
            messagebox.showerror("Ошибка", f"Не удалось запустить ytdl.py:\n{exc}")
            return

        self._set_running(True)

        self.reader_thread = threading.Thread(target=self._reader, daemon=True)
        self.reader_thread.start()

    def _reader(self):
        """Читает stdout процесса в отдельном потоке"""
        proc = self.proc
        try:
            for line in iter(proc.stdout.readline, ""):
                self.queue.put(line)
        except Exception as exc:
            self.queue.put(f"[GUI] Ошибка чтения вывода: {exc}\n")
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            self.queue.put(None)  # сигнал окончания

    def _poll_queue(self):
        """Периодически забирает строки из очереди и обновляет лог"""
        try:
            while True:
                item = self.queue.get_nowait()
                if item is None:
                    self._on_process_finished()
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_queue)

    def _on_process_finished(self):
        """Вызывается, когда поток чтения завершился"""
        rc = None
        if self.proc is not None:
            rc = self.proc.poll()
        self._append_log(f"\n[GUI] Процесс завершён (код: {rc})\n")
        self._set_running(False)

    def _set_running(self, running):
        """Переключает состояние элементов управления"""
        if running:
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _stop(self):
        """Останавливает процесс через terminate()"""
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self._append_log("\n[GUI] Отправлен terminate процессу\n")
            except Exception as exc:
                self._append_log(f"\n[GUI] Не удалось завершить процесс: {exc}\n")

    def _open_folder(self):
        """Открывает папку загрузок в файловом менеджере"""
        path = self.download_dir
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass

        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(path)  # noqa: F821 (Windows only)
            elif system == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{exc}")

    # ------------------------------------------------------------------
    # Закрытие окна
    # ------------------------------------------------------------------
    def _on_close(self):
        """При закрытии окна убивает запущенный процесс"""
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.destroy()


def main():
    app = YtdlApp()
    app.mainloop()


if __name__ == "__main__":
    main()
