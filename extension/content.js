(() => {
  console.log("CONTENT SCRIPT LOADED", window.location.href);

  const EDITABLE_SELECTOR = [
    "textarea:not([disabled]):not([readonly])",
    "input:not([type='hidden']):not([type='checkbox']):not([type='radio']):not([type='button']):not([type='submit']):not([disabled]):not([readonly])",
    "[contenteditable='true']",
    "[contenteditable='plaintext-only']",
    "[role='textbox']"
  ].join(", ");

  const state = {
    allowed: true,
    status: "ready",
    message: "Page connected. Waiting for a typing request.",
    wpm: 65,
    extractedText: "",
    strategy: "none",
    targetLabel: "",
    progress: 0,
    total: 0,
    lastError: ""
  };

  function isVisible(element) {
    return window.OwnedTypingScraper.isElementVisible(element);
  }

  function isEditableCandidate(element) {
    if (!(element instanceof Element)) {
      return false;
    }

    if (!element.matches(EDITABLE_SELECTOR)) {
      return false;
    }

    if (element instanceof HTMLInputElement) {
      const type = (element.type || "text").toLowerCase();
      const supportedTypes = new Set(["text", "search", "email", "url", "tel", "number", "password"]);
      if (!supportedTypes.has(type)) {
        return false;
      }
    }

    return true;
  }

  function getFocusabilityScore(element) {
    if (isVisible(element)) {
      return 240;
    }

    if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
      return 110;
    }

    if (element.isContentEditable) {
      return 80;
    }

    return -120;
  }

  function getElementCenterDistance(a, b) {
    if (!a || !b) {
      return 0;
    }

    const left = a.getBoundingClientRect();
    const right = b.getBoundingClientRect();
    const leftX = left.left + (left.width / 2);
    const leftY = left.top + (left.height / 2);
    const rightX = right.left + (right.width / 2);
    const rightY = right.top + (right.height / 2);
    return Math.hypot(leftX - rightX, leftY - rightY);
  }

  function describeElement(element) {
    if (!element) {
      return "";
    }

    const bits = [element.tagName.toLowerCase()];
    if (element.id) {
      bits.push(`#${element.id}`);
    }

    if (element.name) {
      bits.push(`[name="${element.name}"]`);
    }

    if (element.matches("[contenteditable='true'], [contenteditable='plaintext-only']")) {
      bits.push("[contenteditable]");
    }

    return bits.join("");
  }

  function scoreEditable(element, promptRoot) {
    let score = getFocusabilityScore(element);

    if (element === document.activeElement) {
      score += 320;
    }

    if (promptRoot) {
      const distance = getElementCenterDistance(element, promptRoot);
      score += Math.max(0, 2400 - distance) / 10;

      const elementForm = element.closest("form");
      const promptForm = promptRoot.closest("form");
      if (elementForm && promptForm && elementForm === promptForm) {
        score += 180;
      }
    }

    if (element instanceof HTMLTextAreaElement) {
      score += 120;
    } else if (element instanceof HTMLInputElement) {
      score += 110;
    } else if (element.isContentEditable) {
      score += 100;
    }

    return score;
  }

  function findEditableTarget(promptRoot = null, preferred = null) {
    const candidates = Array.from(document.querySelectorAll(EDITABLE_SELECTOR))
      .filter(isEditableCandidate);

    if (preferred && isEditableCandidate(preferred)) {
      candidates.unshift(preferred);
    }

    if (!candidates.length) {
      return null;
    }

    const uniqueCandidates = Array.from(new Set(candidates));
    const scored = uniqueCandidates
      .map((element) => ({
        element,
        score: scoreEditable(element, promptRoot)
      }))
      .sort((left, right) => right.score - left.score);

    return scored[0] || null;
  }

  function refreshExtraction() {
    const preferredTarget = isEditableCandidate(document.activeElement) ? document.activeElement : null;
    const extraction = window.OwnedTypingScraper.extractVisiblePrompt({
      targetElement: preferredTarget
    });

    state.extractedText = extraction.text || "";
    state.strategy = extraction.strategy || "none";

    return extraction;
  }

  function getRequestedText(rawText) {
    return window.OwnedTypingScraper.normalizeText(rawText || "");
  }

  function updateReadyState(request = {}) {
    const requestedText = getRequestedText(request.customText);
    const target = findEditableTarget(null, document.activeElement);

    if (requestedText) {
      state.extractedText = requestedText;
      state.strategy = "manual";

      if (!target) {
        state.status = "error";
        state.message = "No editable input field was detected on this page.";
        state.targetLabel = "";
        return getPublicState();
      }

      state.status = "ready";
      state.message = `Ready to type ${requestedText.length} pasted characters.`;
      state.targetLabel = describeElement(target.element);
      state.lastError = "";
      return getPublicState();
    }

    const extraction = refreshExtraction();
    const promptTarget = target || findEditableTarget(extraction.root || null, document.activeElement);

    if (!extraction.text) {
      state.status = "error";
      state.message = "No visible typing prompt was found on this page.";
      state.targetLabel = "";
      return getPublicState();
    }

    if (!promptTarget) {
      state.status = "error";
      state.message = "No editable input field was detected on this page.";
      state.targetLabel = "";
      return getPublicState();
    }

    state.status = "ready";
    state.message = `Ready to type ${extraction.text.length} characters using ${extraction.strategy}.`;
    state.targetLabel = describeElement(promptTarget.element);
    state.lastError = "";

    return getPublicState();
  }

  function getPublicState() {
    return {
      ...state,
      pageTitle: document.title,
      hostname: window.location.hostname,
      preview: state.extractedText.slice(0, 140)
    };
  }

  const typer = new window.OwnedTypingTyper.PageTyper({
    onStart(details) {
      state.status = "typing";
      state.message = `Typing ${details.total} characters at ${state.wpm} WPM.`;
      state.progress = 0;
      state.total = details.total;
      state.targetLabel = describeElement(details.element);
      state.lastError = "";
    },
    onProgress(details) {
      state.status = "typing";
      state.progress = details.typed;
      state.total = details.total;
      state.message = `Typing in progress: ${details.typed}/${details.total} characters.`;
    },
    onComplete(details) {
      state.status = "done";
      state.progress = details.typed;
      state.total = details.total;
      state.message = "Typing complete.";
    },
    onStop(details) {
      state.status = "stopped";
      state.progress = details.typed;
      state.total = details.total;
      state.message = "Typing stopped.";
    },
    onError(details) {
      state.status = "error";
      state.lastError = details.error;
      state.message = details.error;
    }
  });

  async function startTyping(request) {
    if (typer.getState().running) {
      state.message = "Typing is already running.";
      return getPublicState();
    }

    const requestedWpm = Math.min(Math.max(Number(request.wpm) || 65, 10), 240);
    const requestedText = getRequestedText(request.customText);
    state.wpm = requestedWpm;

    const extraction = requestedText
      ? {
          text: requestedText,
          root: null,
          strategy: "manual"
        }
      : refreshExtraction();

    const target = findEditableTarget(extraction.root || null, document.activeElement);
    if (!target) {
      state.status = "error";
      state.message = "No editable input field was detected on this page.";
      return getPublicState();
    }

    if (!extraction.text) {
      state.status = "error";
      state.message = "No visible typing prompt was found on this page.";
      return getPublicState();
    }

    state.extractedText = extraction.text;
    state.strategy = extraction.strategy;
    state.targetLabel = describeElement(target.element);
    state.progress = 0;
    state.total = extraction.text.length;
    state.lastError = "";

    try {
      typer.start({
        element: target.element,
        text: extraction.text,
        wpm: requestedWpm
      });
    } catch (error) {
      state.status = "error";
      state.message = error.message || String(error);
      state.lastError = state.message;
    }

    return getPublicState();
  }

  function stopTyping() {
    const stopped = typer.stop();
    if (stopped) {
      state.status = "typing";
      state.message = "Stopping typing...";
    } else if (state.status !== "typing") {
      state.message = "Typing is not currently running.";
    }

    return getPublicState();
  }

  function handleMessage(message, sendResponse) {
    const action = message && message.action;

    if (action === "START") {
      sendResponse({
        status: "ok",
        message: "Content script is connected.",
        hostname: window.location.hostname
      });
      return;
    }

    if (action === "GET_STATE") {
      if (typer.getState().running) {
        sendResponse(getPublicState());
      } else {
        sendResponse(updateReadyState(message || {}));
      }
      return;
    }

    if (action === "START_TYPING") {
      startTyping(message).then(sendResponse);
      return;
    }

    if (action === "STOP_TYPING") {
      sendResponse(stopTyping());
      return;
    }

    sendResponse(getPublicState());
  }

  state.allowed = true;
  state.status = "ready";
  state.message = "Page connected. Waiting for a typing request.";

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("MESSAGE RECEIVED", message, {
      tabId: sender && sender.tab ? sender.tab.id : null,
      url: window.location.href
    });
    handleMessage(message, sendResponse);
    return true;
  });

  updateReadyState();
})();
