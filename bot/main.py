from __future__ import annotations

from browser_controller import BrowserController
from scraper import TypingPageScraper
from state_manager import BotRunConfig, BotStateManager, StopRequested
from typer import TypingEngine
from ui import TypingBotUI


class StandaloneTypingBot:
    def __init__(self, state: BotStateManager) -> None:
        self.state = state

    def stop(self) -> None:
        self.state.request_stop()

    def run(self, config: BotRunConfig) -> None:
        self.state.begin_run()
        self.state.log("Standalone bot started.")

        try:
            with BrowserController(config, self.state) as browser:
                browser.navigate(config.url)

                for attempt in range(1, config.retry_attempts + 1):
                    self.state.raise_if_stop_requested()
                    self.state.log(f"Pipeline attempt {attempt}/{config.retry_attempts}")

                    scraper = TypingPageScraper(
                        page=browser.page,
                        state=self.state,
                        stop_check=self.state.raise_if_stop_requested,
                        stability_interval_ms=config.stability_interval_ms,
                    )
                    typer = TypingEngine(
                        page=browser.page,
                        state=self.state,
                        stop_check=self.state.raise_if_stop_requested,
                    )

                    try:
                        self.state.log("detectPageReady()")
                        page_type = scraper.detect_page_ready(timeout_ms=config.prompt_timeout_ms)

                        self.state.raise_if_stop_requested()
                        self.state.log("waitForPromptReady()")
                        scraper.wait_for_prompt_ready(page_type, timeout_ms=config.prompt_timeout_ms)

                        self.state.raise_if_stop_requested()
                        self.state.log("extractPromptText()")
                        prompt = scraper.extract_prompt_text(page_type, timeout_ms=config.prompt_timeout_ms)

                        self.state.raise_if_stop_requested()
                        self.state.log("normalizeText()")
                        normalized_text = scraper.normalize_text(prompt.text)
                        if not normalized_text:
                            raise RuntimeError("normalizeText() produced an empty prompt.")

                        self.state.log("locateInputField()")
                        input_target = scraper.locate_input_field(timeout_ms=config.prompt_timeout_ms)
                        self.state.log(f"Typing target: {input_target.description}")

                        self.state.raise_if_stop_requested()
                        self.state.log("focusInputField()")
                        scraper.focus_input_field()

                        self.state.raise_if_stop_requested()
                        result = typer.type_text(
                            expected_text=normalized_text,
                            wpm=config.wpm,
                            use_os_fallback=config.use_os_fallback,
                        )

                        self.state.raise_if_stop_requested()
                        self.state.log("verifyTyping()")
                        typer.verify_typing(normalized_text, initial_snapshot=result.initial_snapshot)

                        mode = "OS-level fallback" if result.used_os_fallback else "Playwright keyboard"
                        self.state.log(f"Run completed successfully with {mode}.")
                        break
                    except StopRequested:
                        raise
                    except Exception as error:
                        if attempt >= config.retry_attempts:
                            raise

                        self.state.log(f"Attempt {attempt} failed: {error}")
                        browser.reload()
        except StopRequested:
            self.state.log("Run stopped by user.")
        finally:
            self.state.finish_run()


def main() -> None:
    state = BotStateManager()
    bot = StandaloneTypingBot(state)
    ui = TypingBotUI(
        state=state,
        start_callback=bot.run,
        stop_callback=bot.stop,
    )
    ui.run()


if __name__ == "__main__":
    main()
