from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from queue import Empty, Queue
from threading import Event, Lock
from typing import List, Optional


class StopRequested(Exception):
    """Raised when the user requests the current run to stop."""


@dataclass(slots=True)
class BotRunConfig:
    url: str
    wpm: int = 65
    headless: bool = False
    use_os_fallback: bool = True
    navigation_timeout_ms: int = 20000
    prompt_timeout_ms: int = 10000
    stability_interval_ms: int = 100
    retry_attempts: int = 3
    browser_channel: str = "chrome"
    connect_over_cdp: Optional[str] = None


class BotStateManager:
    def __init__(self) -> None:
        self._stop_event = Event()
        self._log_queue: Queue[str] = Queue()
        self._lock = Lock()
        self._running = False
        self._last_status = "Idle"

    def begin_run(self) -> None:
        with self._lock:
            self._running = True
            self._stop_event.clear()
            self._last_status = "Starting run..."

    def finish_run(self) -> None:
        with self._lock:
            self._running = False
            self._stop_event.clear()
            self._last_status = "Idle"

    def request_stop(self) -> None:
        with self._lock:
            already_requested = self._stop_event.is_set()
            self._stop_event.set()
            self._last_status = "Stop requested."

        if not already_requested:
            self.log("Stop requested.")

    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def raise_if_stop_requested(self) -> None:
        if self.should_stop():
            raise StopRequested("Stop requested by user.")

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        with self._lock:
            self._last_status = message
        print(line, flush=True)
        self._log_queue.put(line)

    def get_last_status(self) -> str:
        with self._lock:
            return self._last_status

    def drain_logs(self) -> List[str]:
        lines: List[str] = []
        while True:
            try:
                lines.append(self._log_queue.get_nowait())
            except Empty:
                return lines
