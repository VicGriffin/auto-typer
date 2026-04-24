from __future__ import annotations

import os
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, scrolledtext
from typing import Callable, Optional

from state_manager import BotRunConfig, BotStateManager, StopRequested


class TypingBotUI:
    def __init__(
        self,
        state: BotStateManager,
        start_callback: Callable[[BotRunConfig], None],
        stop_callback: Callable[[], None],
    ) -> None:
        self.state = state
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.worker_thread: Optional[threading.Thread] = None

        self.root = tk.Tk()
        self.root.title("Standalone Typing Bot")
        self.root.geometry("760x560")
        self.root.minsize(680, 500)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.url_var = tk.StringVar(value="https://www.typingtest.com/")
        self.wpm_var = tk.StringVar(value="65")
        self.status_var = tk.StringVar(value="Idle")

        self._build_layout()
        self._poll_state()

    def run(self) -> None:
        self.root.mainloop()

    def _build_layout(self) -> None:
        frame = tk.Frame(self.root, padx=14, pady=14)
        frame.pack(fill="both", expand=True)

        title = tk.Label(
            frame,
            text="Standalone Desktop Typing Bot",
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        )
        title.pack(fill="x")

        subtitle = tk.Label(
            frame,
            text="Playwright-driven browser automation with optional OS-level typing fallback.",
            fg="#4a5560",
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(2, 12))

        controls = tk.Frame(frame)
        controls.pack(fill="x", pady=(0, 12))

        tk.Label(controls, text="Typing Test URL").grid(row=0, column=0, sticky="w")
        url_entry = tk.Entry(controls, textvariable=self.url_var)
        url_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=(0, 10))

        tk.Label(controls, text="WPM").grid(row=0, column=3, sticky="w")
        wpm_entry = tk.Entry(controls, width=8, textvariable=self.wpm_var)
        wpm_entry.grid(row=1, column=3, sticky="w")

        start_button = tk.Button(controls, text="Start", width=12, command=self._on_start)
        start_button.grid(row=1, column=4, padx=(16, 8))
        self.start_button = start_button

        stop_button = tk.Button(controls, text="Stop", width=12, command=self._on_stop)
        stop_button.grid(row=1, column=5)
        self.stop_button = stop_button

        controls.columnconfigure(0, weight=1)

        status_frame = tk.Frame(frame)
        status_frame.pack(fill="x", pady=(0, 8))
        tk.Label(status_frame, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(status_frame, textvariable=self.status_var, anchor="w").pack(side="left", padx=(8, 0))

        log_frame = tk.Frame(frame)
        log_frame.pack(fill="both", expand=True)
        tk.Label(log_frame, text="Status Log").pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, pady=(6, 0))

    def _build_config(self) -> BotRunConfig:
        url = self.url_var.get().strip()
        if not url:
            raise ValueError("A typing-test URL is required.")

        try:
            wpm = int(self.wpm_var.get().strip())
        except ValueError as error:
            raise ValueError("WPM must be a whole number.") from error

        if wpm < 1 or wpm > 300:
            raise ValueError("WPM must be between 1 and 300.")

        return BotRunConfig(
            url=url,
            wpm=wpm,
            connect_over_cdp=os.getenv("BOT_BROWSER_CDP_URL"),
        )

    def _on_start(self) -> None:
        if self.state.is_running():
            return

        try:
            config = self._build_config()
        except ValueError as error:
            messagebox.showerror("Invalid Configuration", str(error), parent=self.root)
            return

        self.worker_thread = threading.Thread(
            target=self._run_worker,
            args=(config,),
            daemon=True,
        )
        self.worker_thread.start()
        self._refresh_controls()

    def _run_worker(self, config: BotRunConfig) -> None:
        try:
            self.start_callback(config)
        except StopRequested:
            self.state.log("Run stopped.")
        except Exception as error:
            self.state.log(f"Run failed: {error}")
            for line in traceback.format_exc().strip().splitlines():
                self.state.log(line)
        finally:
            self.root.after(0, self._refresh_controls)

    def _on_stop(self) -> None:
        self.stop_callback()
        self._refresh_controls()

    def _on_close(self) -> None:
        self.stop_callback()
        self.root.destroy()

    def _refresh_controls(self) -> None:
        running = self.state.is_running()
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{line}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_state(self) -> None:
        for line in self.state.drain_logs():
            self._append_log(line)

        self.status_var.set(self.state.get_last_status())
        self._refresh_controls()
        self.root.after(150, self._poll_state)
