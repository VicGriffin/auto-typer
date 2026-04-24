from __future__ import annotations

from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from state_manager import BotRunConfig, BotStateManager


class BrowserController:
    def __init__(self, config: BotRunConfig, state: BotStateManager) -> None:
        self.config = config
        self.state = state
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._owns_browser = config.connect_over_cdp is None
        self._owns_context = config.connect_over_cdp is None

    def __enter__(self) -> "BrowserController":
        self.start()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()

    def start(self) -> Page:
        self.state.raise_if_stop_requested()
        self.state.log("Starting Playwright browser controller.")

        self.playwright = sync_playwright().start()
        chromium = self.playwright.chromium

        if self.config.connect_over_cdp:
            self.state.log(f"Connecting to existing browser session at {self.config.connect_over_cdp}.")
            self.browser = chromium.connect_over_cdp(self.config.connect_over_cdp)
            if self.browser.contexts:
                self.context = self.browser.contexts[0]
            else:
                self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000})
                self._owns_context = True
        else:
            launch_kwargs = {"headless": self.config.headless}
            try:
                self.state.log(f"Launching Chromium with channel '{self.config.browser_channel}'.")
                self.browser = chromium.launch(channel=self.config.browser_channel, **launch_kwargs)
            except Exception as error:
                self.state.log(
                    f"Channel launch failed ({error}). Falling back to Playwright Chromium."
                )
                self.browser = chromium.launch(**launch_kwargs)

            self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000})

        self.page = self.context.new_page()

        self.page.set_default_timeout(self.config.navigation_timeout_ms)
        self.page.set_default_navigation_timeout(self.config.navigation_timeout_ms)
        return self.page

    def navigate(self, url: str) -> Page:
        if not self.page:
            raise RuntimeError("Browser page is not available.")

        self.state.raise_if_stop_requested()
        self.state.log(f"Navigating to {url}")
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_load_state("domcontentloaded")
        self.page.bring_to_front()
        return self.page

    def reload(self) -> Page:
        if not self.page:
            raise RuntimeError("Browser page is not available.")

        self.state.raise_if_stop_requested()
        self.state.log("Reloading page for recovery.")
        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_load_state("domcontentloaded")
        self.page.bring_to_front()
        return self.page

    def close(self) -> None:
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass

        if self.context and self._owns_context:
            try:
                self.context.close()
            except Exception:
                pass

        if self.browser and self._owns_browser:
            try:
                self.browser.close()
            except Exception:
                pass

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
