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

  const TEXT_BLOCK_SELECTORS = [
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
    "blockquote",
    "p"
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
    return Math.max(0, 2400 - distance) / 12;
  }

  function getSafeInnerText(element) {
    if (!isElementVisible(element)) {
      return "";
    }

    return normalizeText(element.innerText || element.textContent || "");
  }

  function getTopLevelMatches(selector) {
    return Array.from(document.querySelectorAll(selector)).filter((element) => {
      if (!isElementVisible(element)) {
        return false;
      }

      const parentMatch = element.parentElement && element.parentElement.closest(selector);
      return !parentMatch;
    });
  }

  function scoreCandidate(text, root, strategy, targetElement) {
    if (!text) {
      return null;
    }

    const characterCount = text.length;
    const wordCount = text.split(/\s+/).filter(Boolean).length;
    if (characterCount < 12 || wordCount < 2) {
      return null;
    }

    const alphaCount = (text.match(/[A-Za-z]/g) || []).length;
    const alphaRatio = alphaCount / Math.max(characterCount, 1);
    const distanceScore = getElementDistanceScore(root, targetElement);
    const strategyScore =
      strategy === "word-layout" ? 170 :
      strategy === "letter-layout" ? 150 :
      120;

    const score = (
      strategyScore +
      Math.min(wordCount * 4, 120) +
      Math.min(characterCount, 420) * 0.3 +
      (alphaRatio * 80) +
      distanceScore
    );

    return {
      text,
      root,
      strategy,
      score
    };
  }

  function findClusterRoot(node, selector) {
    let current = node.parentElement;
    let best = null;

    while (current && current !== document.body) {
      const matches = current.querySelectorAll(selector).length;
      if (matches >= 3) {
        best = current;
      }

      if (matches > 80) {
        break;
      }

      current = current.parentElement;
    }

    return best || node.parentElement || document.body;
  }

  function extractFromWordLayout(targetElement) {
    const selector = WORD_SELECTORS.join(",");
    const groupedRoots = new Map();

    for (const node of getTopLevelMatches(selector)) {
      const root = findClusterRoot(node, selector);
      if (!isElementVisible(root)) {
        continue;
      }

      if (!groupedRoots.has(root)) {
        groupedRoots.set(root, new Set());
      }

      groupedRoots.get(root).add(node);
    }

    const candidates = [];
    for (const [root, nodes] of groupedRoots.entries()) {
      const orderedNodes = Array.from(nodes)
        .sort((left, right) => {
          const position = left.compareDocumentPosition(right);
          return position & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
        });

      const words = orderedNodes
        .map((node) => getSafeInnerText(node))
        .filter(Boolean);

      const text = normalizeText(words.join(" "));
      const candidate = scoreCandidate(text, root, "word-layout", targetElement);
      if (candidate) {
        candidates.push(candidate);
      }
    }

    return candidates.sort((left, right) => right.score - left.score)[0] || null;
  }

  function extractFromLetterLayout(targetElement) {
    const selector = LETTER_SELECTORS.join(",");
    const groupedRoots = new Map();

    for (const node of getTopLevelMatches(selector)) {
      const root = findClusterRoot(node, selector);
      if (!isElementVisible(root)) {
        continue;
      }

      if (!groupedRoots.has(root)) {
        groupedRoots.set(root, []);
      }

      groupedRoots.get(root).push(node);
    }

    const candidates = [];
    for (const [root, nodes] of groupedRoots.entries()) {
      if (nodes.length < 8) {
        continue;
      }

      const orderedNodes = nodes
        .slice()
        .sort((left, right) => {
          const position = left.compareDocumentPosition(right);
          return position & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
        });

      const text = normalizeText(
        orderedNodes
          .map((node) => (node.innerText || node.textContent || ""))
          .join("")
      );

      const candidate = scoreCandidate(text, root, "letter-layout", targetElement);
      if (candidate) {
        candidates.push(candidate);
      }
    }

    return candidates.sort((left, right) => right.score - left.score)[0] || null;
  }

  function extractFromTextBlocks(targetElement) {
    const candidates = [];

    for (const selector of TEXT_BLOCK_SELECTORS) {
      for (const element of getTopLevelMatches(selector)) {
        const text = getSafeInnerText(element);
        const candidate = scoreCandidate(text, element, "text-block", targetElement);
        if (candidate) {
          candidates.push(candidate);
        }
      }
    }

    return candidates.sort((left, right) => right.score - left.score)[0] || null;
  }

  function extractVisiblePrompt(options = {}) {
    const targetElement = options.targetElement || null;
    const candidates = [
      extractFromWordLayout(targetElement),
      extractFromLetterLayout(targetElement),
      extractFromTextBlocks(targetElement)
    ].filter(Boolean);

    if (!candidates.length) {
      return {
        text: "",
        root: null,
        strategy: "none",
        score: 0
      };
    }

    return candidates.sort((left, right) => right.score - left.score)[0];
  }

  window.OwnedTypingScraper = {
    extractVisiblePrompt,
    normalizeText,
    isElementVisible
  };
})();
