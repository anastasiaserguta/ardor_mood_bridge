import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import ardor_chroma_bridge as bridge
from ardor_mood_colors import (
    DEFAULT_MOOD_COLORS,
    MOOD_LABELS,
    MOOD_ORDER,
    default_color_config_path,
    load_mood_colors,
    rgb_to_hex,
    save_mood_colors,
)


class QueueLogHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class ArdorMoodBridgeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ardor Mood Bridge")
        self.root.geometry("860x720")
        self.root.minsize(760, 560)

        self.color_config_path = default_color_config_path()
        self.colors = load_mood_colors(self.color_config_path)
        self.swatches = {}
        self.watch_started = False
        self.watch_thread = None
        self.watch_stop_event = None
        self.log_queue = queue.Queue()

        self.path_index_var = tk.StringVar(value="4")
        self.protocol_var = tk.StringVar(value="official_static")
        self.transport_var = tk.StringVar(value="write")
        self.interval_var = tk.StringVar(value="0.2")
        self.brightness_var = tk.StringVar(value="4")
        self.mood_file_var = tk.StringVar(value=bridge.default_mood_file_path())
        self.config_file_var = tk.StringVar(value=self.color_config_path)
        self.status_var = tk.StringVar(value="Готово. Сначала нажми тест цвета или Старт.")

        self._setup_logging()
        self._build_ui()
        self._poll_logs()

    def _setup_logging(self):
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        bridge.logger.addHandler(handler)
        bridge.logger.setLevel(logging.INFO)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        settings = ttk.LabelFrame(self.root, text="Подключение")
        settings.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text="HID index").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Spinbox(settings, from_=0, to=20, width=8, textvariable=self.path_index_var).grid(
            row=0, column=1, padx=8, pady=6, sticky="w"
        )

        ttk.Label(settings, text="Protocol").grid(row=0, column=2, padx=8, pady=6, sticky="w")
        ttk.Combobox(
            settings,
            values=("official_static", "evision_static", "evision_custom", "legacy_direct", "guardian17", "auto"),
            textvariable=self.protocol_var,
            state="readonly",
            width=18,
        ).grid(row=0, column=3, padx=8, pady=6, sticky="w")

        ttk.Label(settings, text="Transport").grid(row=0, column=4, padx=8, pady=6, sticky="w")
        ttk.Combobox(
            settings,
            values=("write", "set_output", "both"),
            textvariable=self.transport_var,
            state="readonly",
            width=12,
        ).grid(row=0, column=5, padx=8, pady=6, sticky="w")

        ttk.Label(settings, text="Mood file").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(settings, textvariable=self.mood_file_var).grid(
            row=1, column=1, columnspan=4, padx=8, pady=6, sticky="ew"
        )
        ttk.Button(settings, text="...", width=4, command=self._choose_mood_file).grid(
            row=1, column=5, padx=8, pady=6, sticky="e"
        )

        ttk.Label(settings, text="Colors").grid(row=2, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(settings, textvariable=self.config_file_var).grid(
            row=2, column=1, columnspan=4, padx=8, pady=6, sticky="ew"
        )
        ttk.Button(settings, text="...", width=4, command=self._choose_config_file).grid(
            row=2, column=5, padx=8, pady=6, sticky="e"
        )

        ttk.Label(settings, text="Interval").grid(row=3, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(settings, textvariable=self.interval_var, width=8).grid(row=3, column=1, padx=8, pady=6, sticky="w")
        ttk.Label(settings, text="Brightness").grid(row=3, column=2, padx=8, pady=6, sticky="w")
        ttk.Spinbox(settings, from_=1, to=4, width=8, textvariable=self.brightness_var).grid(
            row=3, column=3, padx=8, pady=6, sticky="w"
        )
        ttk.Button(settings, text="Старт", command=self._start_watch).grid(row=3, column=4, padx=8, pady=6, sticky="e")
        ttk.Button(settings, text="Стоп", command=self._stop_watch).grid(row=3, column=5, padx=8, pady=6, sticky="e")
        ttk.Button(settings, text="Тест focused", command=lambda: self._test_mood("focused")).grid(
            row=4, column=5, padx=8, pady=6, sticky="e"
        )

        colors_frame = ttk.LabelFrame(self.root, text="Цвета настроений")
        colors_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        colors_frame.columnconfigure(0, weight=1)
        colors_frame.rowconfigure(0, weight=1)

        colors_canvas = tk.Canvas(colors_frame, highlightthickness=0)
        colors_canvas.grid(row=0, column=0, sticky="nsew")
        colors_scrollbar = ttk.Scrollbar(colors_frame, orient="vertical", command=colors_canvas.yview)
        colors_scrollbar.grid(row=0, column=1, sticky="ns")
        colors_canvas.configure(yscrollcommand=colors_scrollbar.set)

        colors_content = ttk.Frame(colors_canvas)
        colors_content.columnconfigure(0, weight=1)
        colors_content.columnconfigure(1, weight=1)
        colors_window = colors_canvas.create_window((0, 0), window=colors_content, anchor="nw")

        def refresh_scroll_region(event=None):
            colors_canvas.configure(scrollregion=colors_canvas.bbox("all"))

        def resize_scroll_content(event):
            colors_canvas.itemconfigure(colors_window, width=event.width)

        def on_mousewheel(event):
            colors_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        colors_content.bind("<Configure>", refresh_scroll_region)
        colors_canvas.bind("<Configure>", resize_scroll_content)
        colors_canvas.bind_all("<MouseWheel>", on_mousewheel)

        for idx, mood in enumerate(MOOD_ORDER):
            self._add_mood_row(colors_content, mood, idx)

        actions = ttk.Frame(self.root)
        actions.grid(row=2, column=0, sticky="ew", padx=12, pady=8)
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(actions, text="Сохранить цвета", command=self._save_colors).grid(row=0, column=1, padx=6)
        ttk.Button(actions, text="Сбросить палитру", command=self._reset_colors).grid(row=0, column=2, padx=6)

        log_frame = ttk.LabelFrame(self.root, text="Лог")
        log_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(8, 12))
        self.root.rowconfigure(3, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=8, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

    def _add_mood_row(self, parent, mood, idx):
        column = idx % 2
        row = idx // 2
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="ew", padx=8, pady=4)
        frame.columnconfigure(1, weight=1)

        hex_color = rgb_to_hex(self.colors[mood])
        swatch = tk.Label(frame, width=4, relief="solid", bg=hex_color)
        swatch.grid(row=0, column=0, padx=(0, 8))
        self.swatches[mood] = swatch

        ttk.Label(frame, text=MOOD_LABELS.get(mood, mood)).grid(row=0, column=1, sticky="w")
        ttk.Button(frame, text="Выбрать", command=lambda m=mood: self._choose_color(m)).grid(row=0, column=2, padx=4)
        ttk.Button(frame, text="Тест", command=lambda m=mood: self._test_mood(m)).grid(row=0, column=3, padx=4)

    def _choose_mood_file(self):
        path = filedialog.askopenfilename(
            title="Выбери ardor_mood.txt",
            initialdir=os.path.dirname(self.mood_file_var.get()) or os.path.expanduser("~"),
            filetypes=(("Mood file", "ardor_mood.txt"), ("Text", "*.txt"), ("All files", "*.*")),
        )
        if path:
            self.mood_file_var.set(path)

    def _choose_config_file(self):
        path = filedialog.asksaveasfilename(
            title="Файл палитры",
            initialfile=os.path.basename(self.config_file_var.get()) or "mood_colors.json",
            initialdir=os.path.dirname(self.config_file_var.get()) or os.path.expanduser("~"),
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("All files", "*.*")),
        )
        if path:
            self.config_file_var.set(path)
            self.color_config_path = path
            if os.path.exists(path):
                self.colors = load_mood_colors(path)
            else:
                self.colors = dict(DEFAULT_MOOD_COLORS)
            self._refresh_swatches()

    def _choose_color(self, mood):
        chosen = colorchooser.askcolor(color=rgb_to_hex(self.colors[mood]), title=MOOD_LABELS.get(mood, mood))
        if chosen and chosen[0]:
            red, green, blue = chosen[0]
            self.colors[mood] = (int(red), int(green), int(blue))
            self._refresh_swatch(mood)

    def _refresh_swatch(self, mood):
        self.swatches[mood].configure(bg=rgb_to_hex(self.colors[mood]))

    def _refresh_swatches(self):
        for mood in self.swatches:
            self._refresh_swatch(mood)

    def _save_colors(self):
        try:
            self.color_config_path = self.config_file_var.get()
            save_mood_colors(self.colors, self.color_config_path)
            bridge.selected_color_config_path = self.color_config_path
            bridge.color_cache = {}
            bridge.color_cache_mtime = None
            self.status_var.set("Цвета сохранены: %s" % self.color_config_path)
        except Exception as exc:
            messagebox.showerror("Не удалось сохранить цвета", str(exc))

    def _reset_colors(self):
        confirmed = messagebox.askyesno(
            "Сбросить палитру?",
            "Вернуть все цвета настроений к дефолтным?\n\n"
            "Текущие несохраненные изменения в окне будут потеряны.",
        )

        if not confirmed:
            self.status_var.set("Сброс палитры отменен.")
            return

        self.colors = dict(DEFAULT_MOOD_COLORS)
        self._refresh_swatches()
        self.status_var.set("Палитра сброшена. Нажми Сохранить цвета.")

    def _configure_bridge(self):
        self._save_colors()
        path_index = int(self.path_index_var.get().strip())
        bridge.configure_bridge(
            path_index=path_index,
            protocol=self.protocol_var.get(),
            transport=self.transport_var.get(),
            brightness=int(self.brightness_var.get().strip()),
            color_config=self.config_file_var.get(),
        )

    def _test_mood(self, mood):
        def worker():
            try:
                self._configure_bridge()
                rgb = self.colors[mood]
                ok = bridge.send_rgb_to_keyboard(*rgb)
                self.status_var.set("%s -> %s" % (MOOD_LABELS.get(mood, mood), "ok" if ok else "ошибка HID"))
            except Exception as exc:
                self.status_var.set("Ошибка: %s" % exc)
                messagebox.showerror("Тест цвета не прошел", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _start_watch(self):
        if self.watch_started:
            self.status_var.set("Watcher уже запущен.")
            return

        def worker():
            try:
                self._configure_bridge()
                interval = float(self.interval_var.get().strip() or "0.2")
                self.watch_stop_event = threading.Event()
                self.watch_thread = bridge.start_mood_watch(self.mood_file_var.get(), interval, self.watch_stop_event)
                self.watch_started = True
                self.status_var.set("Watcher запущен. Можно запускать Sims и переключать активного сима.")
            except Exception as exc:
                self.status_var.set("Ошибка старта: %s" % exc)
                messagebox.showerror("Не удалось запустить watcher", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _stop_watch(self):
        if not self.watch_started or self.watch_stop_event is None:
            self.status_var.set("Watcher уже остановлен.")
            return

        self.watch_stop_event.set()
        self.watch_started = False
        self.watch_thread = None
        self.watch_stop_event = None
        self.status_var.set("Watcher остановлен.")

    def _poll_logs(self):
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")

        self.root.after(200, self._poll_logs)


def main():
    root = tk.Tk()
    app = ArdorMoodBridgeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
