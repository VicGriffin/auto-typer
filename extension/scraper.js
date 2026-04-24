(() => {
  const WORD_SELECTOR = ".word, [data-word], .typing-word, [data-testid*='word']";
  const LETTER_SELECTOR = ".letter, .char, [data-letter], [data-char], [data-testid*='letter']";
  const TEXT_BLOCK_SELECTOR = [
    ".text-block",
    "[data-typing-text]",
    "[data-typing-prompt]",
    "[data-prompt]",
    ".text-to-type",
    ".typing-text",
    ".typing-prompt",
    ".prompt",
    ".quote",
    ".sentence",
    ".paragraph",
    ".passage",
    "blockquote",
    "p"
  ].join(", ");

  const EXCLUDED_SELECTOR = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "img",
    "video",
    "audio",
    "canvas",
    "header",
    "nav",
    "footer",
    "aside",
    "button",
    "input",
    "textarea",
    "select",
    "option",
    "label",
    "[hidden]",
    "[aria-hidden='true']",
    "[role='button']",
    "[role='navigation']",
    "[role='toolbar']",
    "[role='tablist']",
    "[role='tab']"
  ].join(", ");

  const UI_BLACKLIST = [
    /typing assistant/i,
    /words per minute/i,
    /^start$/i,
    /^stop$/i,
    /^status$/i,
    /^current page$/i,
    /^loading active tab/i
  ];

  function normalizeText(text) {
    return String(text || "")
      .replace(/\u00a0/g, " ")
      .replace(/\r/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function isElementVisible(element) {
    if (!(element instanceof Element)) {
      return false;
    }

    if (!element.isConnected) {
      return false;
    }

    if (element.closest("[hidden], [aria-hidden='true']")) {
      return false;
    }

    const style = window.getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.visibility === "collapse" ||
      Number(style.opacity) === 0
    ) {
      return false;
    }

    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isUiNoise(text) {
    const normalized = normalizeText(text);
    if (!normalized) {
      return true;
    }

    return UI_BLACKLIST.some((pattern) => pattern.test(normalized));
  }

  function isExcludedElement(element) {
    if (!(element instanceof Element)) {
      return true;
    }

    if (!isElementVisible(element)) {
      return true;
    }

    if (element.matches(EXCLUDED_SELECTOR) || element.closest(EXCLUDED_SELECTOR)) {
      return true;
    }

    const descriptor = `${element.className || ""} ${element.id || ""}`;
    return /(header|nav|menu|toolbar|footer|sidebar|control|button|banner|promo|advert)/i.test(descriptor);
  }

  function getVisibleMatches(selector, root = document) {
    return Array.from(root.querySelectorAll(selector)).filter((element) => (
      element instanceof Element &&
      isElementVisible(element) &&
      !isExcludedElement(element)
    ));
  }

  function getElementDistance(left, right) {
    if (!(left instanceof Element) || !(right instanceof Element)) {
      return Infinity;
    }

    const leftRect = left.getBoundingClientRect();
    const rightRect = right.getBoundingClientRect();
    const leftX = leftRect.left + (leftRect.width / 2);
    const leftY = leftRect.top + (leftRect.height / 2);
    const rightX = rightRect.left + (rightRect.width / 2);
    const rightY = rightRect.top + (rightRect.height / 2);
    return Math.hypot(leftX - rightX, leftY - rightY);
  }

  function getPromptAnchor(anchorElement = null) {
    if (anchorElement instanceof Element && isElementVisible(anchorElement)) {
      return anchorElement;
    }

    const directTypingInput = document.querySelector("#zz-mob-inp");
    if (directTypingInput instanceof Element && isElementVisible(directTypingInput)) {
      return directTypingInput;
    }

    const active = document.activeElement;
    if (active instanceof Element && isElementVisible(active)) {
      return active;
    }

    const fallback = document.querySelector(
      "input:not([type='hidden']), textarea, [contenteditable='true'], [contenteditable='plaintext-only']"
    );
    return fallback instanceof Element && isElementVisible(fallback) ? fallback : null;
  }

  function findNearestMatch(selector, anchorElement = null) {
    const matches = getVisibleMatches(selector);
    if (!matches.length) {
      return null;
    }

    const anchor = getPromptAnchor(anchorElement);
    if (!(anchor instanceof Element)) {
      return matches[0] || null;
    }

    return matches
      .slice()
      .sort((left, right) => getElementDistance(left, anchor) - getElementDistance(right, anchor))[0] || null;
  }

  function findClusterContainer(startElement, selector, minimumCount) {
    if (!(startElement instanceof Element)) {
      return null;
    }

    let current = startElement.parentElement;
    let fallback = startElement.parentElement;

    while (current && current !== document.documentElement) {
      if (isElementVisible(current) && !isExcludedElement(current)) {
        fallback = current;
        if (current.querySelectorAll(selector).length >= minimumCount) {
          return current;
        }
      }

      current = current.parentElement;
    }

    return fallback;
  }

  function findTextBlockContainer(anchorElement = null) {
    const anchor = getPromptAnchor(anchorElement);
    const candidates = getVisibleMatches(TEXT_BLOCK_SELECTOR)
      .filter((element) => {
        const text = normalizeText(element.textContent || "");
        return text.length >= 12 && !isUiNoise(text);
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const anchorRect = anchor instanceof Element ? anchor.getBoundingClientRect() : null;
        let score = normalizeText(element.textContent || "").length;

        if (anchorRect) {
          const verticalGap = anchorRect.top - rect.bottom;
          if (verticalGap >= -20 && verticalGap <= 320) {
            score += 1000 - Math.abs(verticalGap);
          } else if (rect.top <= anchorRect.bottom && rect.bottom >= anchorRect.top) {
            score += 400;
          } else {
            score -= Math.abs(verticalGap);
          }

          score -= getElementDistance(element, anchor) / 10;
        }

        return { element, score };
      })
      .sort((left, right) => right.score - left.score);

    return candidates[0] ? candidates[0].element : null;
  }

  function detectPageType(anchorElement = null) {
    if (findNearestMatch(WORD_SELECTOR, anchorElement)) {
      return "word";
    }

    if (findNearestMatch(LETTER_SELECTOR, anchorElement)) {
      return "letter";
    }

    if (findTextBlockContainer(anchorElement)) {
      return "text-block";
    }

    return null;
  }

  function locatePromptContainer(pageType, anchorElement = null) {
    if (pageType === "word") {
      const word = findNearestMatch(WORD_SELECTOR, anchorElement);
      return findClusterContainer(word, WORD_SELECTOR, 2);
    }

    if (pageType === "letter") {
      const letter = findNearestMatch(LETTER_SELECTOR, anchorElement);
      return findClusterContainer(letter, LETTER_SELECTOR, 6);
    }

    if (pageType === "text-block") {
      return findTextBlockContainer(anchorElement);
    }

    return null;
  }

  function extractWordText(container) {
    const words = getVisibleMatches(WORD_SELECTOR, container)
      .map((element) => normalizeText(element.textContent || ""))
      .filter((text) => text && !isUiNoise(text));

    return normalizeText(words.join(" "));
  }

  function extractLetterText(container) {
    const letters = getVisibleMatches(LETTER_SELECTOR, container)
      .map((element) => element.textContent || "")
      .join("");

    return normalizeText(letters);
  }

  function extractTextBlock(container) {
    if (!(container instanceof Element)) {
      return "";
    }

    const parts = [];
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          const parent = node.parentElement;
          if (!(parent instanceof Element)) {
            return NodeFilter.FILTER_REJECT;
          }

          if (isExcludedElement(parent)) {
            return NodeFilter.FILTER_REJECT;
          }

          const text = normalizeText(node.textContent || "");
          if (!text || isUiNoise(text)) {
            return NodeFilter.FILTER_REJECT;
          }

          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    let current = walker.nextNode();
    while (current) {
      const text = normalizeText(current.textContent || "");
      if (text && !isUiNoise(text)) {
        parts.push(text);
      }
      current = walker.nextNode();
    }

    return normalizeText(parts.join(" "));
  }

  function extractStructuredText(pageType, container) {
    if (!(container instanceof Element)) {
      return "";
    }

    if (pageType === "word") {
      return extractWordText(container);
    }

    if (pageType === "letter") {
      return extractLetterText(container);
    }

    if (pageType === "text-block") {
      return extractTextBlock(container);
    }

    return "";
  }

  window.OwnedTypingScraper = {
    WORD_SELECTOR,
    LETTER_SELECTOR,
    TEXT_BLOCK_SELECTOR,
    detectPageType,
    locatePromptContainer,
    extractStructuredText,
    normalizeText,
    isElementVisible
  };
})();
