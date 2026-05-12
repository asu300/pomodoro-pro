"""
番茄钟 - Python + Tkinter
功能：计时、开始/暂停/重置、番茄/休息切换、音效提醒、番茄计数、自定义时长
"""

import tkinter as tk
from tkinter import ttk, messagebox
import winsound
import threading


class PomodoroTimer:
    # 默认时间（分钟）
    DEFAULT_WORK = 25
    DEFAULT_SHORT_BREAK = 5
    DEFAULT_LONG_BREAK = 15

    # 状态颜色
    COLOR_BG = "#2d2d2d"
    COLOR_FG = "#ffffff"
    COLOR_WORK = "#e74c3c"
    COLOR_BREAK = "#27ae60"
    COLOR_LONG_BREAK = "#2980b9"
    COLOR_ACCENT = "#f39c12"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("番茄钟")
        self.root.geometry("400x520")
        self.root.resizable(False, False)
        self.root.configure(bg=self.COLOR_BG)

        # 状态变量
        self.is_running = False
        self.is_work = True  # True=工作, False=休息
        self.remaining_seconds = self.DEFAULT_WORK * 60
        self.completed_pomodoros = 0
        self.timer_id = None

        # 可自定义时长
        self.work_minutes = tk.IntVar(value=self.DEFAULT_WORK)
        self.short_break_minutes = tk.IntVar(value=self.DEFAULT_SHORT_BREAK)
        self.long_break_minutes = tk.IntVar(value=self.DEFAULT_LONG_BREAK)

        self._build_ui()
        self._update_display()

    def _build_ui(self):
        # 标题
        title = tk.Label(
            self.root, text="番茄钟", font=("Microsoft YaHei", 20, "bold"),
            bg=self.COLOR_BG, fg=self.COLOR_ACCENT
        )
        title.pack(pady=(20, 5))

        # 状态标签
        self.status_label = tk.Label(
            self.root, text="工作时间", font=("Microsoft YaHei", 14),
            bg=self.COLOR_BG, fg=self.COLOR_WORK
        )
        self.status_label.pack(pady=(0, 10))

        # 计时器显示
        self.time_label = tk.Label(
            self.root, text="25:00", font=("Consolas", 64, "bold"),
            bg=self.COLOR_BG, fg=self.COLOR_FG
        )
        self.time_label.pack(pady=(10, 20))

        # 按钮区域
        btn_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        btn_frame.pack(pady=10)

        self.start_btn = tk.Button(
            btn_frame, text="开始", font=("Microsoft YaHei", 12),
            bg=self.COLOR_WORK, fg="white", width=8, relief="flat",
            command=self._toggle_timer
        )
        self.start_btn.grid(row=0, column=0, padx=5)

        reset_btn = tk.Button(
            btn_frame, text="重置", font=("Microsoft YaHei", 12),
            bg="#7f8c8d", fg="white", width=8, relief="flat",
            command=self._reset
        )
        reset_btn.grid(row=0, column=1, padx=5)

        skip_btn = tk.Button(
            btn_frame, text="跳过", font=("Microsoft YaHei", 12),
            bg="#8e44ad", fg="white", width=8, relief="flat",
            command=self._skip
        )
        skip_btn.grid(row=0, column=2, padx=5)

        # 番茄计数
        self.count_label = tk.Label(
            self.root, text="已完成: 0 个番茄", font=("Microsoft YaHei", 12),
            bg=self.COLOR_BG, fg=self.COLOR_ACCENT
        )
        self.count_label.pack(pady=(25, 5))

        # 番茄图标（用 ● 表示）
        self.dots_label = tk.Label(
            self.root, text="", font=("Arial", 16),
            bg=self.COLOR_BG, fg=self.COLOR_WORK
        )
        self.dots_label.pack(pady=(0, 15))

        # 分隔线
        sep = ttk.Separator(self.root, orient="horizontal")
        sep.pack(fill="x", padx=30, pady=5)

        # 设置区域
        settings_label = tk.Label(
            self.root, text="自定义时长（分钟）", font=("Microsoft YaHei", 10),
            bg=self.COLOR_BG, fg="#95a5a6"
        )
        settings_label.pack(pady=(10, 5))

        settings_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        settings_frame.pack()

        # 工作时长
        tk.Label(settings_frame, text="工作:", font=("Microsoft YaHei", 10),
                 bg=self.COLOR_BG, fg=self.COLOR_FG).grid(row=0, column=0, padx=5)
        work_spin = tk.Spinbox(
            settings_frame, from_=1, to=60, width=4, textvariable=self.work_minutes,
            font=("Consolas", 11), justify="center",
            command=self._on_settings_change
        )
        work_spin.grid(row=0, column=1, padx=5)
        work_spin.bind("<Return>", lambda e: self._on_settings_change())

        # 短休息
        tk.Label(settings_frame, text="短休:", font=("Microsoft YaHei", 10),
                 bg=self.COLOR_BG, fg=self.COLOR_FG).grid(row=0, column=2, padx=5)
        short_spin = tk.Spinbox(
            settings_frame, from_=1, to=30, width=4, textvariable=self.short_break_minutes,
            font=("Consolas", 11), justify="center",
            command=self._on_settings_change
        )
        short_spin.grid(row=0, column=3, padx=5)
        short_spin.bind("<Return>", lambda e: self._on_settings_change())

        # 长休息
        tk.Label(settings_frame, text="长休:", font=("Microsoft YaHei", 10),
                 bg=self.COLOR_BG, fg=self.COLOR_FG).grid(row=0, column=4, padx=5)
        long_spin = tk.Spinbox(
            settings_frame, from_=1, to=30, width=4, textvariable=self.long_break_minutes,
            font=("Consolas", 11), justify="center",
            command=self._on_settings_change
        )
        long_spin.grid(row=0, column=5, padx=5)
        long_spin.bind("<Return>", lambda e: self._on_settings_change())

        # 音效提示 checkbox
        self.sound_enabled = tk.BooleanVar(value=True)
        sound_cb = tk.Checkbutton(
            self.root, text="音效提醒", variable=self.sound_enabled,
            font=("Microsoft YaHei", 10), bg=self.COLOR_BG, fg=self.COLOR_FG,
            selectcolor=self.COLOR_BG, activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_FG
        )
        sound_cb.pack(pady=(10, 0))

    def _on_settings_change(self):
        """设置变化时，如果计时器未运行，更新显示"""
        if not self.is_running:
            self._update_remaining_for_mode()
            self._update_display()

    def _update_remaining_for_mode(self):
        """根据当前模式更新剩余时间"""
        if self.is_work:
            self.remaining_seconds = self.work_minutes.get() * 60
        else:
            if self.completed_pomodoros > 0 and self.completed_pomodoros % 4 == 0:
                self.remaining_seconds = self.long_break_minutes.get() * 60
            else:
                self.remaining_seconds = self.short_break_minutes.get() * 60

    def _toggle_timer(self):
        if self.is_running:
            self._pause()
        else:
            self._start()

    def _start(self):
        self.is_running = True
        self.start_btn.config(text="暂停", bg="#f39c12")
        self._tick()

    def _pause(self):
        self.is_running = False
        self.start_btn.config(text="继续", bg=self.COLOR_WORK)
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

    def _reset(self):
        self.is_running = False
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        self.is_work = True
        self.remaining_seconds = self.work_minutes.get() * 60
        self.completed_pomodoros = 0
        self.start_btn.config(text="开始", bg=self.COLOR_WORK)
        self._update_display()
        self._update_status()
        self._update_count()

    def _skip(self):
        """跳过当前阶段"""
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        self.is_running = False
        self._on_timer_complete()

    def _tick(self):
        if not self.is_running:
            return
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._update_display()
            self.timer_id = self.root.after(1000, self._tick)
        else:
            self.is_running = False
            self._on_timer_complete()

    def _on_timer_complete(self):
        """计时结束处理"""
        if self.is_work:
            self.completed_pomodoros += 1
            self._update_count()

        # 播放音效
        if self.sound_enabled.get():
            threading.Thread(target=self._play_sound, daemon=True).start()

        # 切换模式
        self.is_work = not self.is_work

        if self.is_work:
            self.remaining_seconds = self.work_minutes.get() * 60
        else:
            # 每4个番茄后长休息
            if self.completed_pomodoros % 4 == 0 and self.completed_pomodoros > 0:
                self.remaining_seconds = self.long_break_minutes.get() * 60
            else:
                self.remaining_seconds = self.short_break_minutes.get() * 60

        self.start_btn.config(text="开始", bg=self.COLOR_WORK)
        self._update_display()
        self._update_status()

        # 弹窗提示
        if self.is_work:
            title = "休息结束"
            msg = "休息结束，开始新的番茄吧！"
        else:
            if self.completed_pomodoros % 4 == 0:
                title = "长休息时间"
                msg = f"已完成 {self.completed_pomodoros} 个番茄！好好休息一下吧！"
            else:
                title = "短休息时间"
                msg = f"第 {self.completed_pomodoros} 个番茄完成！休息 5 分钟吧。"

        # 非阻塞提示（窗口置顶闪一下）
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False))
        messagebox.showinfo(title, msg)

    def _play_sound(self):
        """播放系统提示音"""
        try:
            # 播放两声系统提示音
            for _ in range(2):
                winsound.Beep(800, 300)
                winsound.Beep(1200, 300)
        except Exception:
            # 回退到系统默认声音
            winsound.MessageBeep(winsound.MB_OK)

    def _update_display(self):
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        self.time_label.config(text=f"{minutes:02d}:{seconds:02d}")

    def _update_status(self):
        if self.is_work:
            self.status_label.config(text="工作时间", fg=self.COLOR_WORK)
        else:
            if self.completed_pomodoros % 4 == 0 and self.completed_pomodoros > 0:
                self.status_label.config(text="长休息", fg=self.COLOR_LONG_BREAK)
            else:
                self.status_label.config(text="短休息", fg=self.COLOR_BREAK)

    def _update_count(self):
        self.count_label.config(text=f"已完成: {self.completed_pomodoros} 个番茄")
        dots = "● " * self.completed_pomodoros
        self.dots_label.config(text=dots)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PomodoroTimer()
    app.run()
