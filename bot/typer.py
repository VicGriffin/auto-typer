from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from state_manager import BotStateManager


INPUT_MARKER = "data-bot-input-field"


class TypingFailure(RuntimeError):
    def __init__(self, message: str, typed_length: int) -> None:
        super().__init__(message)
        self.typed_length = typed_length


@dataclass(slots=True)
class TypingResult:
    initial_snapshot: str
    typed_length: int
    used_os_fallback: bool


class TypingEngine:
    def __init__(
        self,
        page: Page,
        state: BotStateManager,
        stop_check: Callable[[], None],
    ) -> None:
        self.page = page
        self.state = state
        self.stop_check = stop_check

    def type_text(self, expected_text: str, wpm: int, use_os_fallback: bool = True) -> TypingResult:
        self._focus_target()
        initial_snapshot = self._get_target_snapshot()

        try:
            typed_length = self._type_with_playwright(expected_text, wpm, initial_snapshot)
            return TypingResult(
                initial_snapshot=initial_snapshot,
                typed_length=typed_length,
                used_os_fallback=False,
            )
        except TypingFailure as error:
            if use_os_fallback and error.typed_length == 0:
                self.state.log(f"Playwright typing failed early ({error}). Falling back to OS keystrokes.")
                self._focus_target()
                typed_length = self._type_with_os_keystrokes(expected_text, wpm, initial_snapshot)
                return TypingResult(
                    initial_snapshot=initial_snapshot,
                    typed_length=typed_length,
                    used_os_fallback=True,
                )

            raise

    def verify_typing(self, expected_text: str, initial_snapshot: str = "") -> None:
        current_snapshot = self._get_target_snapshot()
        typed_portion = self._typed_portion(initial_snapshot, current_snapshot)
        if typed_portion != expected_text:
            raise RuntimeError(
                f"verifyTyping() failed. Expected {len(expected_text)} chars but found {len(typed_portion)} chars."
            )
        self.state.log("verifyTyping() -> typed text matches expected prompt")

    def _type_with_playwright(self, expected_text: str, wpm: int, initial_snapshot: str) -> int:
        self.state.log("typeText() -> using Playwright keyboard")
        delay_ms = self._character_delay_ms(wpm)
        progress_step = max(len(expected_text) // 20, 1)

        for index, character in enumerate(expected_text, start=1):
            self.stop_check()
            self._send_playwright_key(character, delay_ms)
            typed_portion = self._wait_for_expected_prefix(
                initial_snapshot=initial_snapshot,
                expected_prefix=expected_text[:index],
                timeout_ms=max(delay_ms * 4, 800),
            )

            if not self._progress_matches(typed_portion, expected_text):
                raise TypingFailure("Typing diverged from the expected prompt.", len(typed_portion))

            if index == len(expected_text) or index % progress_step == 0:
                self.state.log(f"typeText() -> {index}/{len(expected_text)} characters typed")

        return len(expected_text)

    def _type_with_os_keystrokes(self, expected_text: str, wpm: int, initial_snapshot: str) -> int:
        try:
            import pyautogui
        except Exception as error:  # pragma: no cover - import environment specific
            raise RuntimeError(f"OS-level typing fallback is unavailable: {error}") from error

        self.state.log("typeText() -> using OS-level keystrokes")
        delay_seconds = self._character_delay_ms(wpm) / 1000
        pyautogui.PAUSE = delay_seconds
        pyautogui.FAILSAFE = True

        progress_step = max(len(expected_text) // 20, 1)

        for index, character in enumerate(expected_text, start=1):
            self.stop_check()
            self._send_os_key(pyautogui, character)
            typed_portion = self._wait_for_expected_prefix(
                initial_snapshot=initial_snapshot,
                expected_prefix=expected_text[:index],
                timeout_ms=max(int(delay_seconds * 4000), 800),
            )

            if not self._progress_matches(typed_portion, expected_text):
                raise TypingFailure("OS-level typing diverged from the expected prompt.", len(typed_portion))

            if index == len(expected_text) or index % progress_step == 0:
                self.state.log(f"typeText() -> {index}/{len(expected_text)} characters typed")

        return len(expected_text)

    def _focus_target(self) -> None:
        target = self.page.locator(f"[{INPUT_MARKER}='true']").first
        target.wait_for(state="visible", timeout=5000)

        try:
            target.scroll_into_view_if_needed(timeout=2000)
        except PlaywrightError:
            pass

        try:
            target.click(timeout=2000)
        except PlaywrightError:
            target.focus()

        self.page.bring_to_front()
        self.page.wait_for_function(
            """
            (inputMarker) => {
              const active = document.activeElement;
              return Boolean(active && active.getAttribute && active.getAttribute(inputMarker) === "true");
            }
            """,
            arg=INPUT_MARKER,
            timeout=2000,
        )

    def _send_playwright_key(self, character: str, delay_ms: int) -> None:
        if character == "\n":
            self.page.keyboard.press("Enter", delay=delay_ms)
            return

        if character == "\t":
            self.page.keyboard.press("Tab", delay=delay_ms)
            return

        if character == " ":
            self.page.keyboard.press("Space", delay=delay_ms)
            return

        self.page.keyboard.type(character, delay=delay_ms)

    def _send_os_key(self, pyautogui, character: str) -> None:
        if character == "\n":
            pyautogui.press("enter", interval=0)
            return

        if character == "\t":
            pyautogui.press("tab", interval=0)
            return

        if character == " ":
            pyautogui.press("space", interval=0)
            return

        pyautogui.write(character, interval=0)

    def _wait_for_expected_prefix(self, initial_snapshot: str, expected_prefix: str, timeout_ms: int) -> str:
        try:
            self.page.wait_for_function(
                """
                (payload) => {
                  const target = document.querySelector(`[${payload.inputMarker}="true"]`);
                  if (!(target instanceof Element)) return false;

                  let current = "";
                  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
                    current = String(target.value || "");
                  } else if (target.isContentEditable) {
                    current = String(target.textContent || "");
                  } else {
                    current = String(target.textContent || "");
                  }

                  const typed = current.startsWith(payload.initialSnapshot)
                    ? current.slice(payload.initialSnapshot.length)
                    : current;

                  return typed === payload.expectedPrefix || !payload.expectedPrefix.startsWith(typed);
                }
                """,
                arg={
                    "inputMarker": INPUT_MARKER,
                    "initialSnapshot": initial_snapshot,
                    "expectedPrefix": expected_prefix,
                },
                timeout=timeout_ms,
            )
        except PlaywrightError:
            typed_portion = self._typed_portion(initial_snapshot, self._get_target_snapshot())
            raise TypingFailure(
                "Timed out while waiting for the input field to reflect typed progress.",
                len(typed_portion),
            )

        return self._typed_portion(initial_snapshot, self._get_target_snapshot())

    def _get_target_snapshot(self) -> str:
        return self.page.evaluate(
            """
            (inputMarker) => {
              const target = document.querySelector(`[${inputMarker}="true"]`);
              if (!(target instanceof Element)) return "";
              if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
                return String(target.value || "");
              }
              if (target.isContentEditable) {
                return String(target.textContent || "");
              }
              return String(target.textContent || "");
            }
            """,
            INPUT_MARKER,
        )

    @staticmethod
    def _typed_portion(initial_snapshot: str, current_snapshot: str) -> str:
        if current_snapshot.startswith(initial_snapshot):
            return current_snapshot[len(initial_snapshot):]
        return current_snapshot

    @staticmethod
    def _progress_matches(typed_portion: str, expected_text: str) -> bool:
        return typed_portion == expected_text[: len(typed_portion)]

    @staticmethod
    def _character_delay_ms(wpm: int) -> int:
        safe_wpm = max(int(wpm), 1)
        characters_per_minute = safe_wpm * 5
        return max(int((60000 / characters_per_minute)), 1)
