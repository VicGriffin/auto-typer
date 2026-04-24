from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from state_manager import BotStateManager


WORD_SELECTOR = ".word, [data-word], .typing-word, [data-testid*='word']"
LETTER_SELECTOR = ".letter, .char, [data-letter], [data-char], [data-testid*='letter']"
TEXT_BLOCK_SELECTOR = (
    ".text-block, [data-typing-text], [data-typing-prompt], [data-prompt], "
    ".text-to-type, .typing-text, .typing-prompt, .prompt, .quote, .sentence, "
    ".paragraph, .passage, blockquote, p"
)
EDITABLE_INPUT_SELECTOR = (
    "input:not([type='hidden']):not([type='checkbox']):not([type='radio']):"
    "not([type='button']):not([type='submit']):not([disabled]):not([readonly]), "
    "textarea:not([disabled]):not([readonly])"
)
CONTENTEDITABLE_SELECTOR = "[contenteditable='true'], [contenteditable='plaintext-only'], [role='textbox']"
PROMPT_MARKER = "data-bot-prompt-container"
INPUT_MARKER = "data-bot-input-field"


@dataclass(slots=True)
class PromptText:
    page_type: str
    container_description: str
    text: str


@dataclass(slots=True)
class InputTarget:
    description: str


class TypingPageScraper:
    def __init__(
        self,
        page: Page,
        state: BotStateManager,
        stop_check: Callable[[], None],
        stability_interval_ms: int = 100,
    ) -> None:
        self.page = page
        self.state = state
        self.stop_check = stop_check
        self.stability_interval_ms = max(int(stability_interval_ms), 50)
        self._stable_prompt_text = ""
        self._stable_prompt_container_description: Optional[str] = None
        self._stable_page_type: Optional[str] = None

    def detect_page_ready(self, timeout_ms: int = 10000) -> str:
        self.stop_check()
        self.page.wait_for_load_state("domcontentloaded")
        self._wait_for_interactable_input(timeout_ms)
        input_target = self.locate_input_field(timeout_ms=timeout_ms)
        page_type = self._wait_for_page_type(timeout_ms)
        self._wait_for_prompt_visibility(page_type, timeout_ms)
        self.state.log("PAGE READY")
        self.state.log(f"INPUT FOUND: {input_target is not None}")
        self.state.log(f"detectPageReady() -> {page_type}")
        return page_type

    def detect_page_type(self) -> Optional[str]:
        return self.page.evaluate(
            """
            (selectors) => {
              const isVisible = (element) => {
                if (!(element instanceof Element) || !element.isConnected) return false;
                if (element.closest("[hidden], [aria-hidden='true']")) return false;
                const style = window.getComputedStyle(element);
                const isTransparentEditable = element.matches(
                  `${selectors.directInput}, ${selectors.contenteditable}, #zz-mob-inp`
                );
                if (
                  style.display === "none" ||
                  style.visibility === "hidden" ||
                  (Number(style.opacity) === 0 && !isTransparentEditable)
                ) {
                  return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isExcluded = (element) => {
                if (!(element instanceof Element)) return true;
                if (element.matches(selectors.excluded) || element.closest(selectors.excluded)) return true;
                const descriptor = `${element.className || ""} ${element.id || ""}`;
                return /(header|nav|menu|toolbar|footer|sidebar|control|button|banner|promo|advert)/i.test(descriptor);
              };

              const anchor = (
                document.querySelector(`[${selectors.inputMarker}="true"]`) ||
                document.querySelector("#zz-mob-inp") ||
                document.activeElement ||
                document.querySelector(`${selectors.directInput}, ${selectors.contenteditable}`)
              );

              const visibleMatches = (selector) => (
                [...document.querySelectorAll(selector)].filter((element) => isVisible(element) && !isExcluded(element))
              );

              const getDistance = (left, right) => {
                if (!(left instanceof Element) || !(right instanceof Element)) return Number.POSITIVE_INFINITY;
                const leftRect = left.getBoundingClientRect();
                const rightRect = right.getBoundingClientRect();
                const leftX = leftRect.left + (leftRect.width / 2);
                const leftY = leftRect.top + (leftRect.height / 2);
                const rightX = rightRect.left + (rightRect.width / 2);
                const rightY = rightRect.top + (rightRect.height / 2);
                return Math.hypot(leftX - rightX, leftY - rightY);
              };

              const nearestCount = (selector) => {
                const matches = visibleMatches(selector);
                if (!(anchor instanceof Element)) return matches.length;
                return matches
                  .sort((left, right) => getDistance(left, anchor) - getDistance(right, anchor))
                  .slice(0, 12)
                  .length;
              };

              if (nearestCount(selectors.word) >= 2) return "word";
              if (nearestCount(selectors.letter) >= 6) return "letter";

              const textBlocks = visibleMatches(selectors.textBlock).filter((element) => {
                const text = String(element.textContent || "").replace(/\\s+/g, " ").trim();
                return text.length >= 12;
              });
              return textBlocks.length ? "text-block" : null;
            }
            """,
            {
                "word": WORD_SELECTOR,
                "letter": LETTER_SELECTOR,
                "textBlock": TEXT_BLOCK_SELECTOR,
                "directInput": EDITABLE_INPUT_SELECTOR,
                "contenteditable": CONTENTEDITABLE_SELECTOR,
                "inputMarker": INPUT_MARKER,
                "excluded": self._excluded_selector(),
            },
        )

    def wait_for_prompt_ready(self, page_type: str, timeout_ms: int = 5000) -> str:
        self.stop_check()
        self._wait_for_prompt_visibility(page_type, timeout_ms)

        attempts = max(timeout_ms // self.stability_interval_ms, 3)
        previous = ""
        stable_count = 0

        for _ in range(attempts):
            self.stop_check()
            container_description = self.locate_prompt_container(page_type)
            current = ""
            if container_description:
                current = self.normalize_text(self.extract_structured_text(page_type))

            if current and current == previous:
                stable_count += 1
                if stable_count >= 3:
                    self._stable_page_type = page_type
                    self._stable_prompt_text = current
                    self._stable_prompt_container_description = container_description
                    self.state.log("waitForPromptReady() -> prompt text stabilized")
                    return current
            else:
                stable_count = 0

            previous = current
            self.page.wait_for_timeout(self.stability_interval_ms)

        if previous:
            self._stable_page_type = page_type
            self._stable_prompt_text = previous
            self._stable_prompt_container_description = self.locate_prompt_container(page_type)
            self.state.log("waitForPromptReady() -> using latest stable prompt snapshot")
            return previous

        raise RuntimeError("Prompt text never stabilized before timeout.")

    def locate_prompt_container(self, page_type: str) -> Optional[str]:
        result = self.page.evaluate(
            """
            (payload) => {
              const {
                pageType,
                wordSelector,
                letterSelector,
                textBlockSelector,
                editableInputSelector,
                contenteditableSelector,
                promptMarker,
                inputMarker,
                excludedSelector,
              } = payload;

              const clearMarkers = () => {
                document.querySelectorAll(`[${promptMarker}]`).forEach((element) => {
                  element.removeAttribute(promptMarker);
                });
              };

              const normalize = (text) => String(text || "").replace(/\\s+/g, " ").trim();

              const isVisible = (element) => {
                if (!(element instanceof Element) || !element.isConnected) return false;
                if (element.closest("[hidden], [aria-hidden='true']")) return false;
                const style = window.getComputedStyle(element);
                const isTransparentEditable = element.matches(
                  `${editableInputSelector}, ${contenteditableSelector}, #zz-mob-inp`
                );
                if (
                  style.display === "none" ||
                  style.visibility === "hidden" ||
                  (Number(style.opacity) === 0 && !isTransparentEditable)
                ) {
                  return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isExcluded = (element) => {
                if (!(element instanceof Element)) return true;
                if (element.matches(excludedSelector) || element.closest(excludedSelector)) return true;
                const descriptor = `${element.className || ""} ${element.id || ""}`;
                return /(header|nav|menu|toolbar|footer|sidebar|control|button|banner|promo|advert)/i.test(descriptor);
              };

              const getDistance = (left, right) => {
                if (!(left instanceof Element) || !(right instanceof Element)) return Number.POSITIVE_INFINITY;
                const leftRect = left.getBoundingClientRect();
                const rightRect = right.getBoundingClientRect();
                const leftX = leftRect.left + (leftRect.width / 2);
                const leftY = leftRect.top + (leftRect.height / 2);
                const rightX = rightRect.left + (rightRect.width / 2);
                const rightY = rightRect.top + (rightRect.height / 2);
                return Math.hypot(leftX - rightX, leftY - rightY);
              };

              const describe = (element) => {
                if (!(element instanceof Element)) return "";
                return `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ""}`;
              };

              const getAnchor = () => {
                const markedInput = document.querySelector(`[${inputMarker}="true"]`);
                if (markedInput instanceof Element && isVisible(markedInput)) return markedInput;

                const explicit = document.querySelector("#zz-mob-inp");
                if (explicit instanceof Element && isVisible(explicit)) return explicit;

                const active = document.activeElement;
                if (active instanceof Element && isVisible(active)) return active;

                const editable = document.querySelector(`${editableInputSelector}, ${contenteditableSelector}`);
                return editable instanceof Element && isVisible(editable) ? editable : null;
              };

              const visibleMatches = (selector, root = document) => (
                [...root.querySelectorAll(selector)].filter((element) => isVisible(element) && !isExcluded(element))
              );

              const findClusterContainer = (startElement, selector, minimumCount) => {
                if (!(startElement instanceof Element)) return null;
                let current = startElement.parentElement;
                let fallback = startElement.parentElement;

                while (current && current !== document.documentElement) {
                  if (isVisible(current) && !isExcluded(current)) {
                    fallback = current;
                    if (visibleMatches(selector, current).length >= minimumCount) {
                      return current;
                    }
                  }
                  current = current.parentElement;
                }

                return fallback;
              };

              const findTextBlock = (anchor) => {
                const candidates = visibleMatches(textBlockSelector)
                  .filter((element) => normalize(element.textContent || "").length >= 12)
                  .map((element) => {
                    const rect = element.getBoundingClientRect();
                    const anchorRect = anchor instanceof Element ? anchor.getBoundingClientRect() : null;
                    let score = normalize(element.textContent || "").length;

                    if (anchorRect) {
                      const verticalGap = anchorRect.top - rect.bottom;
                      if (verticalGap >= -20 && verticalGap <= 320) {
                        score += 1000 - Math.abs(verticalGap);
                      } else if (rect.top <= anchorRect.bottom && rect.bottom >= anchorRect.top) {
                        score += 400;
                      } else {
                        score -= Math.abs(verticalGap);
                      }
                      score -= getDistance(element, anchor) / 10;
                    }

                    return { element, score };
                  })
                  .sort((left, right) => right.score - left.score);

                return candidates[0] ? candidates[0].element : null;
              };

              clearMarkers();
              const anchor = getAnchor();
              let container = null;

              if (pageType === "word") {
                const words = visibleMatches(wordSelector).sort((left, right) => getDistance(left, anchor) - getDistance(right, anchor));
                container = findClusterContainer(words[0], wordSelector, 2);
              } else if (pageType === "letter") {
                const letters = visibleMatches(letterSelector).sort((left, right) => getDistance(left, anchor) - getDistance(right, anchor));
                container = findClusterContainer(letters[0], letterSelector, 6);
              } else if (pageType === "text-block") {
                container = findTextBlock(anchor);
              }

              if (!(container instanceof Element)) return null;
              container.setAttribute(promptMarker, "true");
              return describe(container);
            }
            """,
            {
                "pageType": page_type,
                "wordSelector": WORD_SELECTOR,
                "letterSelector": LETTER_SELECTOR,
                "textBlockSelector": TEXT_BLOCK_SELECTOR,
                "editableInputSelector": EDITABLE_INPUT_SELECTOR,
                "contenteditableSelector": CONTENTEDITABLE_SELECTOR,
                "promptMarker": PROMPT_MARKER,
                "inputMarker": INPUT_MARKER,
                "excludedSelector": self._excluded_selector(),
            },
        )
        return result

    def extract_structured_text(self, page_type: str) -> str:
        return self.page.evaluate(
            """
            (payload) => {
              const {
                pageType,
                wordSelector,
                letterSelector,
                promptMarker,
                excludedSelector,
                uiBlacklist,
              } = payload;

              const container = document.querySelector(`[${promptMarker}="true"]`);
              if (!(container instanceof Element)) return "";

              const normalize = (text) => String(text || "").replace(/\\s+/g, " ").trim();
              const isUiNoise = (text) => {
                const normalized = normalize(text);
                if (!normalized) return true;
                return uiBlacklist.some((pattern) => new RegExp(pattern, "i").test(normalized));
              };

              const isVisible = (element) => {
                if (!(element instanceof Element) || !element.isConnected) return false;
                if (element.closest("[hidden], [aria-hidden='true']")) return false;
                const style = window.getComputedStyle(element);
                if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
                  return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isExcluded = (element) => {
                if (!(element instanceof Element)) return true;
                if (element.matches(excludedSelector) || element.closest(excludedSelector)) return true;
                const descriptor = `${element.className || ""} ${element.id || ""}`;
                return /(header|nav|menu|toolbar|footer|sidebar|control|button|banner|promo|advert)/i.test(descriptor);
              };

              if (pageType === "word") {
                return normalize(
                  [...container.querySelectorAll(wordSelector)]
                    .filter((element) => isVisible(element) && !isExcluded(element))
                    .map((element) => normalize(element.textContent || ""))
                    .filter((text) => text && !isUiNoise(text))
                    .join(" ")
                );
              }

              if (pageType === "letter") {
                return normalize(
                  [...container.querySelectorAll(letterSelector)]
                    .filter((element) => isVisible(element) && !isExcluded(element))
                    .map((element) => element.textContent || "")
                    .join("")
                );
              }

              const parts = [];
              const walker = document.createTreeWalker(
                container,
                NodeFilter.SHOW_TEXT,
                {
                  acceptNode(node) {
                    const parent = node.parentElement;
                    if (!(parent instanceof Element)) return NodeFilter.FILTER_REJECT;
                    if (!isVisible(parent) || isExcluded(parent)) return NodeFilter.FILTER_REJECT;
                    const text = normalize(node.textContent || "");
                    if (!text || isUiNoise(text)) return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                  }
                }
              );

              let current = walker.nextNode();
              while (current) {
                const text = normalize(current.textContent || "");
                if (text && !isUiNoise(text)) {
                  parts.push(text);
                }
                current = walker.nextNode();
              }

              return normalize(parts.join(" "));
            }
            """,
            {
                "pageType": page_type,
                "wordSelector": WORD_SELECTOR,
                "letterSelector": LETTER_SELECTOR,
                "promptMarker": PROMPT_MARKER,
                "excludedSelector": self._excluded_selector(),
                "uiBlacklist": [
                    "typing assistant",
                    "words per minute",
                    "^start$",
                    "^stop$",
                    "^status$",
                    "^current page$",
                    "^loading active tab",
                ],
            },
        )

    def normalize_text(self, text: str) -> str:
        return " ".join(str(text or "").split()).strip()

    def extract_prompt_text(self, page_type: str, timeout_ms: int = 5000) -> PromptText:
        if self._stable_page_type != page_type or not self._stable_prompt_text:
            self.wait_for_prompt_ready(page_type, timeout_ms=timeout_ms)

        container_description = self._stable_prompt_container_description or self.locate_prompt_container(page_type)
        normalized = self.normalize_text(self._stable_prompt_text)

        if not container_description:
            raise RuntimeError("Could not locate the prompt container.")
        if not normalized:
            raise RuntimeError("Could not extract prompt text from the page.")

        self.state.log(f"TEXT LENGTH: {len(normalized)}")
        self.state.log(f"TEXT SAMPLE: {normalized[:100]}")
        self.state.log(f"extractPromptText() -> {len(normalized)} characters from {container_description}")
        return PromptText(page_type=page_type, container_description=container_description, text=normalized)

    def locate_input_field(self, timeout_ms: int = 10000) -> InputTarget:
        self.stop_check()
        self._wait_for_interactable_input(timeout_ms)
        description = self.page.evaluate(
            """
            (payload) => {
              const {
                editableInputSelector,
                contenteditableSelector,
                promptMarker,
                inputMarker,
              } = payload;

              const clearMarker = () => {
                document.querySelectorAll(`[${inputMarker}]`).forEach((element) => {
                  element.removeAttribute(inputMarker);
                });
              };

              const isVisible = (element) => {
                if (!(element instanceof Element) || !element.isConnected) return false;
                if (element.closest("[hidden], [aria-hidden='true']")) return false;
                const style = window.getComputedStyle(element);
                const isTransparentEditable = element.matches(
                  `${editableInputSelector}, ${contenteditableSelector}, #zz-mob-inp`
                );
                if (
                  style.display === "none" ||
                  style.visibility === "hidden" ||
                  (Number(style.opacity) === 0 && !isTransparentEditable)
                ) {
                  return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isEditable = (element) => {
                if (!(element instanceof Element) || !isVisible(element)) return false;
                if (!element.matches(`${editableInputSelector}, ${contenteditableSelector}`)) return false;
                if (element instanceof HTMLInputElement) {
                  const supportedTypes = new Set(["text", "search", "email", "url", "tel", "number", "password"]);
                  return supportedTypes.has(String(element.type || "text").toLowerCase());
                }
                return true;
              };

              const describe = (element) => {
                if (!(element instanceof Element)) return "";
                return `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ""}`;
              };

              const promptContainer = document.querySelector(`[${promptMarker}="true"]`);
              const getDistance = (left, right) => {
                if (!(left instanceof Element) || !(right instanceof Element)) return Number.POSITIVE_INFINITY;
                const leftRect = left.getBoundingClientRect();
                const rightRect = right.getBoundingClientRect();
                const leftX = leftRect.left + (leftRect.width / 2);
                const leftY = leftRect.top + (leftRect.height / 2);
                const rightX = rightRect.left + (rightRect.width / 2);
                const rightY = rightRect.top + (rightRect.height / 2);
                return Math.hypot(leftX - rightX, leftY - rightY);
              };

              const sortByDistance = (elements) => {
                if (!(promptContainer instanceof Element)) return elements;
                return elements.sort((left, right) => getDistance(left, promptContainer) - getDistance(right, promptContainer));
              };

              clearMarker();

              const active = document.activeElement;
              if (isEditable(active)) {
                active.setAttribute(inputMarker, "true");
                active.focus({ preventScroll: false });
                return describe(active);
              }

              const directInputs = sortByDistance(
                [...document.querySelectorAll(editableInputSelector)].filter(isEditable)
              );
              if (directInputs.length) {
                directInputs[0].setAttribute(inputMarker, "true");
                directInputs[0].focus({ preventScroll: false });
                return describe(directInputs[0]);
              }

              const editableContainers = sortByDistance(
                [...document.querySelectorAll(contenteditableSelector)].filter(isEditable)
              );
              if (editableContainers.length) {
                editableContainers[0].setAttribute(inputMarker, "true");
                editableContainers[0].focus({ preventScroll: false });
                return describe(editableContainers[0]);
              }

              return null;
            }
            """,
            {
                "editableInputSelector": EDITABLE_INPUT_SELECTOR,
                "contenteditableSelector": CONTENTEDITABLE_SELECTOR,
                "promptMarker": PROMPT_MARKER,
                "inputMarker": INPUT_MARKER,
            },
        )

        if not description:
            raise RuntimeError("Could not locate an interactable typing input.")

        self.state.log(f"locateInputField() -> {description}")
        return InputTarget(description=description)

    def focus_input_field(self) -> None:
        self.stop_check()
        target = self.page.locator(f"[{INPUT_MARKER}='true']").first
        target.wait_for(state="visible", timeout=5000)

        try:
            target.scroll_into_view_if_needed(timeout=2000)
        except PlaywrightError:
            pass

        try:
            target.click(timeout=3000)
        except PlaywrightError:
            target.focus()

        self.page.bring_to_front()
        self.state.log("focusInputField() -> target focused")

    def _wait_for_interactable_input(self, timeout_ms: int) -> None:
        self.page.wait_for_function(
            """
            (selectors) => {
              const isVisible = (element) => {
                if (!(element instanceof Element) || !element.isConnected) return false;
                if (element.closest("[hidden], [aria-hidden='true']")) return false;
                const style = window.getComputedStyle(element);
                const isTransparentEditable = element.matches(
                  `${selectors.direct}, ${selectors.contenteditable}, #zz-mob-inp`
                );
                if (
                  style.display === "none" ||
                  style.visibility === "hidden" ||
                  (Number(style.opacity) === 0 && !isTransparentEditable)
                ) {
                  return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isEditable = (element) => {
                if (!(element instanceof Element) || !isVisible(element)) return false;
                if (!element.matches(`${selectors.direct}, ${selectors.contenteditable}`)) return false;
                if (element instanceof HTMLInputElement) {
                  const supportedTypes = new Set(["text", "search", "email", "url", "tel", "number", "password"]);
                  return supportedTypes.has(String(element.type || "text").toLowerCase());
                }
                return true;
              };

              const active = document.activeElement;
              if (isEditable(active)) return true;

              return [...document.querySelectorAll(`${selectors.direct}, ${selectors.contenteditable}`)].some(isEditable);
            }
            """,
            arg={
                "direct": EDITABLE_INPUT_SELECTOR,
                "contenteditable": CONTENTEDITABLE_SELECTOR,
            },
            timeout=timeout_ms,
        )

    def _wait_for_page_type(self, timeout_ms: int) -> str:
        self.page.wait_for_function(
            """
            (selectors) => {
              const isVisible = (element) => {
                if (!(element instanceof Element) || !element.isConnected) return false;
                if (element.closest("[hidden], [aria-hidden='true']")) return false;
                const style = window.getComputedStyle(element);
                if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
                  return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isExcluded = (element) => {
                if (!(element instanceof Element)) return true;
                if (element.matches(selectors.excluded) || element.closest(selectors.excluded)) return true;
                const descriptor = `${element.className || ""} ${element.id || ""}`;
                return /(header|nav|menu|toolbar|footer|sidebar|control|button|banner|promo|advert)/i.test(descriptor);
              };

              const visibleMatches = (selector) => (
                [...document.querySelectorAll(selector)].filter((element) => isVisible(element) && !isExcluded(element))
              );

              if (visibleMatches(selectors.word).length >= 2) return true;
              if (visibleMatches(selectors.letter).length >= 6) return true;
              return visibleMatches(selectors.textBlock).some((element) => (
                String(element.textContent || "").replace(/\\s+/g, " ").trim().length >= 12
              ));
            }
            """,
            arg={
                "word": WORD_SELECTOR,
                "letter": LETTER_SELECTOR,
                "textBlock": TEXT_BLOCK_SELECTOR,
                "excluded": self._excluded_selector(),
            },
            timeout=timeout_ms,
        )

        page_type = self.detect_page_type()
        if not page_type:
            raise RuntimeError("Could not detect a supported typing-test layout on the page.")
        return page_type

    def _wait_for_prompt_visibility(self, page_type: str, timeout_ms: int) -> None:
        selector = {
            "word": WORD_SELECTOR,
            "letter": LETTER_SELECTOR,
            "text-block": TEXT_BLOCK_SELECTOR,
        }.get(page_type)

        if not selector:
            raise RuntimeError(f"Unsupported page type: {page_type}")

        self.page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
        self.page.wait_for_function(
            """
            (payload) => {
              const {
                pageType,
                promptMarker,
                inputMarker,
                wordSelector,
                letterSelector,
                textBlockSelector,
                editableInputSelector,
                contenteditableSelector,
                excludedSelector,
              } = payload;

              const normalize = (text) => String(text || "").replace(/\\s+/g, " ").trim();
              const isVisible = (element) => {
                if (!(element instanceof Element) || !element.isConnected) return false;
                if (element.closest("[hidden], [aria-hidden='true']")) return false;
                const style = window.getComputedStyle(element);
                if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
                  return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              };

              const isExcluded = (element) => {
                if (!(element instanceof Element)) return true;
                if (element.matches(excludedSelector) || element.closest(excludedSelector)) return true;
                const descriptor = `${element.className || ""} ${element.id || ""}`;
                return /(header|nav|menu|toolbar|footer|sidebar|control|button|banner|promo|advert)/i.test(descriptor);
              };

              const getAnchor = () => {
                const markedInput = document.querySelector(`[${inputMarker}="true"]`);
                if (markedInput instanceof Element && isVisible(markedInput)) return markedInput;
                const explicit = document.querySelector("#zz-mob-inp");
                if (explicit instanceof Element && isVisible(explicit)) return explicit;
                const active = document.activeElement;
                if (active instanceof Element && isVisible(active)) return active;
                const editable = document.querySelector(`${editableInputSelector}, ${contenteditableSelector}`);
                return editable instanceof Element && isVisible(editable) ? editable : null;
              };

              const getDistance = (left, right) => {
                if (!(left instanceof Element) || !(right instanceof Element)) return Number.POSITIVE_INFINITY;
                const leftRect = left.getBoundingClientRect();
                const rightRect = right.getBoundingClientRect();
                const leftX = leftRect.left + (leftRect.width / 2);
                const leftY = leftRect.top + (leftRect.height / 2);
                const rightX = rightRect.left + (rightRect.width / 2);
                const rightY = rightRect.top + (rightRect.height / 2);
                return Math.hypot(leftX - rightX, leftY - rightY);
              };

              const visibleMatches = (selectorValue) => (
                [...document.querySelectorAll(selectorValue)].filter((element) => isVisible(element) && !isExcluded(element))
              );

              const findTextBlock = (anchor) => {
                const candidates = visibleMatches(textBlockSelector)
                  .filter((element) => normalize(element.textContent || "").length >= 12)
                  .sort((left, right) => getDistance(left, anchor) - getDistance(right, anchor));
                return candidates[0] || null;
              };

              const anchor = getAnchor();
              if (!(anchor instanceof Element)) return false;

              if (pageType === "word") {
                return visibleMatches(wordSelector).length >= 2;
              }
              if (pageType === "letter") {
                return visibleMatches(letterSelector).length >= 6;
              }
              return Boolean(findTextBlock(anchor));
            }
            """,
            arg={
                "pageType": page_type,
                "promptMarker": PROMPT_MARKER,
                "inputMarker": INPUT_MARKER,
                "wordSelector": WORD_SELECTOR,
                "letterSelector": LETTER_SELECTOR,
                "textBlockSelector": TEXT_BLOCK_SELECTOR,
                "editableInputSelector": EDITABLE_INPUT_SELECTOR,
                "contenteditableSelector": CONTENTEDITABLE_SELECTOR,
                "excludedSelector": self._excluded_selector(),
            },
            timeout=timeout_ms,
        )

    @staticmethod
    def _excluded_selector() -> str:
        return (
            "script, style, noscript, template, svg, img, video, audio, canvas, header, nav, footer, "
            "aside, button, select, option, label, [hidden], [aria-hidden='true'], [role='button'], "
            "[role='navigation'], [role='toolbar'], [role='tablist'], [role='tab']"
        )
