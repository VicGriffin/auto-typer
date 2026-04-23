(() => {
  const WORD_SELECTORS = [
    ".word",
    "[data-word]",
    ".typing-word",
    "[data-testid*='word']"
  ];

  const LETTER_SELECTORS = [
    ".letter",
    ".char",
    "[data-letter]",
    "[data-char]",
    "[data-testid*='letter']"
  ];

  const PROMPT_CONTAINER_SELECTORS = [
    "[data-typing-text]",
    "[data-typing-prompt]",
    "[data-prompt]",
    ".text-block",
    ".text-to-type",
    ".typing-text",
    ".typing-prompt",
    ".prompt",
    ".quote",
    ".sentence",
    ".paragraph",
    ".passage",
    "[class*='prompt']",
    "[class*='passage']",
    "[class*='quote']",
    "[class*='typing']",
    "[class*='text']",
    "blockquote",
    "p"
  ];

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

  const UI_TEXT_PATTERNS = [
    /typing assistant/i,
    /words per minute/i,
    /^start$/i,
    /^stop$/i,
    /^status$/i,
    /^current page$/i,
    /^loading active tab/i
  ];

  function normalizeText(text) {
    if (!text) {
      return "";
    }

    const normalizedLines = String(text)
      .replace(/\u00a0/g, " ")
      .replace(/\r/g, "")
      .split("\n")
      .map((line) => line.replace(/\s+/g, " ").trim());

    const compact = [];
    for (const line of normalizedLines) {
      if (!line) {
        if (compact.length && compact[compact.length - 1] !== "") {
          compact.push("");
        }
        continue;
      }

      compact.push(line);
    }

    return compact.join("\n").replace(/\n{3,}/g, "\n\n").trim();
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

  function getElementDistanceScore(element, targetElement) {
    if (!targetElement || !(targetElement instanceof Element)) {
      return 0;
    }

    const a = element.getBoundingClientRect();
    const b = targetElement.getBoundingClientRect();
    const ax = a.left + (a.width / 2);
    const ay = a.top + (a.height / 2);
    const bx = b.left + (b.width / 2);
    const by = b.top + (b.height / 2);
    const distance = Math.hypot(ax - bx, ay - by);
    return Math.max(0, 2600 - distance) / 10;
  }

  function getNormalizedElementText(element) {
    if (!(element instanceof Element) || !isElementVisible(element)) {
      return "";
    }

    return normalizeText(element.innerText || element.textContent || "");
  }

  function isUiText(text) {
    const compact = normalizeText(text);
    if (!compact) {
      return true;
    }

    return UI_TEXT_PATTERNS.some((pattern) => pattern.test(compact));
  }

  function isExcludedElement(element) {
    if (!(element instanceof Element)) {
      return true;
    }

    if (!isElementVisible(element)) {
      return true;
    }

    if (element.closest(EXCLUDED_SELECTOR)) {
      return true;
    }

    const classAndId = `${element.className || ""} ${element.id || ""}`;
    if (/(header|nav|menu|toolbar|footer|sidebar|control|button|banner|promo|advert)/i.test(classAndId)) {
      return true;
    }

    return false;
  }

  function sanitizePromptText(text) {
    const compact = normalizeText(text);
    if (!compact) {
      return "";
    }

    const filteredLines = compact
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .filter((line) => !isUiText(line));

    const deduped = [];
    for (const line of filteredLines) {
      if (deduped[deduped.length - 1] !== line) {
        deduped.push(line);
      }
    }

    return normalizeText(deduped.join(" "))
      .replace(/\s+([,.;!?])/g, "$1")
      .trim();
  }

  function getContainerHintScore(element) {
    if (!(element instanceof Element)) {
      return 0;
    }

    const descriptor = `${element.className || ""} ${element.id || ""} ${element.tagName || ""}`;
    let score = 0;

    if (/(prompt|passage|quote|typing|text)/i.test(descriptor)) {
      score += 120;
    }

    if (element.matches(".text-block, .typing-text, .typing-prompt, [data-typing-text], [data-typing-prompt], [data-prompt]")) {
      score += 220;
    }

    if (element.querySelector(WORD_SELECTORS.join(","))) {
      score += 260;
    }

    if (element.querySelector(LETTER_SELECTORS.join(","))) {
      score += 170;
    }

    return score;
  }

  function scoreText(text, container, strategy, targetElement) {
    if (!text) {
      return -Infinity;
    }

    const words = text.split(/\s+/).filter(Boolean);
    if (text.length < 12 || words.length < 2) {
      return -Infinity;
    }

    const alphaCount = (text.match(/[A-Za-z]/g) || []).length;
    const alphaRatio = alphaCount / Math.max(text.length, 1);
    const strategyScore =
      strategy === "word-layout" ? 320 :
      strategy === "letter-layout" ? 250 :
      strategy === "structured-block" ? 210 :
      150;

    return (
      strategyScore +
      getContainerHintScore(container) +
      getElementDistanceScore(container, targetElement) +
      Math.min(words.length * 5, 160) +
      Math.min(text.length, 420) * 0.25 +
      (alphaRatio * 80)
    );
  }

  function addCandidate(candidates, seen, element) {
    if (!(element instanceof Element)) {
      return;
    }

    if (seen.has(element)) {
      return;
    }

    if (element === document.body) {
      return;
    }

    if (!isElementVisible(element) || isExcludedElement(element)) {
      return;
    }

    const text = getNormalizedElementText(element);
    if (!text || isUiText(text)) {
      return;
    }

    seen.add(element);
    candidates.push(element);
  }

  function addNearbyPromptCandidates(anchor, candidates, seen) {
    if (!(anchor instanceof Element)) {
      return;
    }

    let current = anchor;
    for (let depth = 0; current && current !== document.body && depth < 6; depth += 1) {
      const parent = current.parentElement;
      if (!parent) {
        break;
      }

      addCandidate(candidates, seen, parent.closest(PROMPT_CONTAINER_SELECTORS.join(",")));

      for (const sibling of Array.from(parent.children)) {
        if (sibling === current) {
          continue;
        }

        if (sibling.matches(PROMPT_CONTAINER_SELECTORS.join(","))) {
          addCandidate(candidates, seen, sibling);
        }

        for (const nested of sibling.querySelectorAll(PROMPT_CONTAINER_SELECTORS.join(","))) {
          addCandidate(candidates, seen, nested);
        }
      }

      current = parent;
    }
  }

  function findPromptContainers(targetElement) {
    const candidates = [];
    const seen = new Set();
    const input = document.querySelector("#zz-mob-inp");
    const anchor = (targetElement instanceof Element && isElementVisible(targetElement))
      ? targetElement
      : (input instanceof Element ? input : null);

    if (anchor) {
      addNearbyPromptCandidates(anchor, candidates, seen);
    }

    for (const selector of PROMPT_CONTAINER_SELECTORS) {
      for (const element of document.querySelectorAll(selector)) {
        addCandidate(candidates, seen, element);
      }
    }

    if (!candidates.length && document.body) {
      candidates.push(document.body);
    }

    return candidates;
  }

  function extractFromWordNodes(container) {
    const nodes = Array.from(container.querySelectorAll(WORD_SELECTORS.join(",")))
      .filter((element) => !isExcludedElement(element))
      .map((element) => sanitizePromptText(getNormalizedElementText(element)))
      .filter(Boolean);

    if (!nodes.length) {
      return null;
    }

    return sanitizePromptText(nodes.join(" "));
  }

  function extractFromLetterNodes(container) {
    const nodes = Array.from(container.querySelectorAll(LETTER_SELECTORS.join(",")))
      .filter((element) => !isExcludedElement(element));

    if (nodes.length < 8) {
      return null;
    }

    const text = sanitizePromptText(
      nodes
        .map((element) => getNormalizedElementText(element))
        .filter(Boolean)
        .join("")
    );

    return text || null;
  }

  function extractFromStructuredNodes(container) {
    const nodes = Array.from(container.querySelectorAll("p, span, blockquote"))
      .filter((element) => !isExcludedElement(element))
      .filter((element) => {
        const text = sanitizePromptText(getNormalizedElementText(element));
        if (!text) {
          return false;
        }

        const parentStructured = element.parentElement && element.parentElement.closest("p, span, blockquote");
        return !parentStructured || parentStructured === container || !container.contains(parentStructured);
      });

    if (!nodes.length) {
      return null;
    }

    const textSegments = nodes
      .map((element) => sanitizePromptText(getNormalizedElementText(element)))
      .filter(Boolean);

    if (!textSegments.length) {
      return null;
    }

    const averageLength = textSegments.join("").length / textSegments.length;
    if (nodes.length > 40 && averageLength < 2.5) {
      return null;
    }

    return sanitizePromptText(textSegments.join(" "));
  }

  function extractWithTreeWalker(container) {
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

          const text = sanitizePromptText(node.textContent || "");
          if (!text) {
            return NodeFilter.FILTER_REJECT;
          }

          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    let current = walker.nextNode();
    while (current) {
      const text = sanitizePromptText(current.textContent || "");
      if (text) {
        parts.push(text);
      }
      current = walker.nextNode();
    }

    return sanitizePromptText(parts.join(" "));
  }

  function extractFromContainer(container, targetElement) {
    if (!(container instanceof Element)) {
      return null;
    }

    const strategies = [
      {
        name: "word-layout",
        run: () => extractFromWordNodes(container)
      },
      {
        name: "letter-layout",
        run: () => extractFromLetterNodes(container)
      },
      {
        name: "structured-block",
        run: () => extractFromStructuredNodes(container)
      },
      {
        name: "container-treewalker",
        run: () => extractWithTreeWalker(container)
      }
    ];

    for (const strategy of strategies) {
      const text = strategy.run();
      if (!text) {
        continue;
      }

      const score = scoreText(text, container, strategy.name, targetElement);
      if (!Number.isFinite(score)) {
        continue;
      }

      return {
        text,
        root: container,
        strategy: strategy.name,
        score
      };
    }

    return null;
  }

  function extractVisiblePrompt(options = {}) {
    const requestedTarget = options.targetElement instanceof Element ? options.targetElement : null;
    const targetElement = requestedTarget || document.querySelector("#zz-mob-inp") || null;
    const containers = findPromptContainers(targetElement);
    const candidates = containers
      .map((container) => extractFromContainer(container, targetElement))
      .filter(Boolean)
      .sort((left, right) => right.score - left.score);

    if (!candidates.length) {
      console.log("SCRAPER INPUT:", null);
      console.log("SCRAPER OUTPUT:", "");
      return {
        text: "",
        root: null,
        strategy: "none",
        score: 0
      };
    }

    const best = candidates[0];
    console.log("SCRAPER INPUT:", best.root);
    console.log("SCRAPER OUTPUT:", best.text);
    return best;
  }

  window.OwnedTypingScraper = {
    extractVisiblePrompt,
    normalizeText,
    isElementVisible
  };
})();
