(() => {
  console.log("CONTENT SCRIPT LOADED", window.location.href);

  const EDITABLE_INPUT_SELECTOR = [
    "input:not([type='hidden']):not([type='checkbox']):not([type='radio']):not([type='button']):not([type='submit']):not([disabled]):not([readonly])",
    "textarea:not([disabled]):not([readonly])"
  ].join(", ");

  const CONTENTEDITABLE_SELECTOR = [
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

  let pendingContextPromise = null;
  let pendingContextKey = "";

  function sleep(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function isVisible(element) {
    return window.OwnedTypingScraper.isElementVisible(element);
  }

  function isEditableCandidate(element) {
    if (!(element instanceof Element)) {
      return false;
    }

    if (!isVisible(element)) {
      return false;
    }

    if (!element.matches(`${EDITABLE_INPUT_SELECTOR}, ${CONTENTEDITABLE_SELECTOR}`)) {
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

  function focusEditable(element) {
    if (element && typeof element.focus === "function") {
      element.focus({ preventScroll: false });
    }
  }

  function describeElement(element) {
    if (!element) {
      return "";
    }

    const bits = [element.tagName.toLowerCase()];
    if (element.id) {
      bits.push(`#${element.id}`);
    }

    if (element.getAttribute("name")) {
      bits.push(`[name="${element.getAttribute("name")}"]`);
    }

    if (element.matches("[contenteditable='true'], [contenteditable='plaintext-only']")) {
      bits.push("[contenteditable]");
    }

    return bits.join("");
  }

  function getElementCenterDistance(left, right) {
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

  function getRequestedText(rawText) {
    return window.OwnedTypingScraper.normalizeText(rawText || "");
  }

  function getPromptAnchorElement() {
    const directTypingInput = document.querySelector("#zz-mob-inp");
    if (directTypingInput instanceof Element && isVisible(directTypingInput)) {
      return directTypingInput;
    }

    const active = document.activeElement;
    if (isEditableCandidate(active)) {
      return active;
    }

    const input = document.querySelector(EDITABLE_INPUT_SELECTOR);
    if (input instanceof Element && isVisible(input)) {
      return input;
    }

    const editable = document.querySelector(CONTENTEDITABLE_SELECTOR);
    return editable instanceof Element && isVisible(editable) ? editable : null;
  }

  function detectPageType() {
    const type = window.OwnedTypingScraper.detectPageType(getPromptAnchorElement());
    console.log("PAGE TYPE:", type);
    return type;
  }

  async function waitForStableText(getTextFn, timeout = 5000) {
    let last = "";
    let stableCount = 0;
    const attempts = Math.max(Math.floor(timeout / 100), 1);

    for (let index = 0; index < attempts; index += 1) {
      const current = getTextFn();

      if (current && current === last) {
        stableCount += 1;
        if (stableCount >= 3) {
          return current;
        }
      } else if (current !== last) {
        stableCount = 0;
      }

      last = current;
      await sleep(100);
    }

    return last;
  }

  function locatePromptContainer(pageType) {
    return window.OwnedTypingScraper.locatePromptContainer(pageType, getPromptAnchorElement());
  }

  function extractStructuredText(pageType, container) {
    return window.OwnedTypingScraper.extractStructuredText(pageType, container);
  }

  function normalizeText(text) {
    return window.OwnedTypingScraper.normalizeText(text);
  }

  async function waitForPromptReady(pageType) {
    let latestContainer = null;
    const text = await waitForStableText(() => {
      latestContainer = locatePromptContainer(pageType);
      if (!(latestContainer instanceof Element)) {
        return "";
      }

      return normalizeText(extractStructuredText(pageType, latestContainer));
    });

    return {
      container: latestContainer,
      text
    };
  }

  function sortByPromptDistance(candidates, promptContainer) {
    if (!(promptContainer instanceof Element)) {
      return candidates;
    }

    return candidates
      .slice()
      .sort((left, right) => getElementCenterDistance(left, promptContainer) - getElementCenterDistance(right, promptContainer));
  }

  function locateInputField(promptContainer = null) {
    const active = document.activeElement;
    if (isEditableCandidate(active)) {
      focusEditable(active);
      console.log("TARGET INPUT:", active);
      return active;
    }

    const directInputs = sortByPromptDistance(
      Array.from(document.querySelectorAll(EDITABLE_INPUT_SELECTOR)).filter(isEditableCandidate),
      promptContainer
    );
    if (directInputs.length) {
      focusEditable(directInputs[0]);
      console.log("TARGET INPUT:", directInputs[0]);
      return directInputs[0];
    }

    const editableContainers = sortByPromptDistance(
      Array.from(document.querySelectorAll(CONTENTEDITABLE_SELECTOR)).filter(isEditableCandidate),
      promptContainer
    );
    if (editableContainers.length) {
      focusEditable(editableContainers[0]);
      console.log("TARGET INPUT:", editableContainers[0]);
      return editableContainers[0];
    }

    console.log("TARGET INPUT:", null);
    return null;
  }

  function verifyProgress(details) {
    const typedValue = String(details.typedValue || "");
    const expectedText = String(details.expectedText || "");
    return typedValue === expectedText.slice(0, typedValue.length);
  }

  async function prepareTypingContext(request = {}) {
    const requestedText = getRequestedText(request.customText);
    if (requestedText) {
      console.log("PAGE TYPE:", "manual");
      console.log("CONTAINER:", null);
      console.log("EXTRACTED TEXT:", requestedText);

      const input = locateInputField(null);
      if (!input) {
        return {
          error: "No editable input field was detected on this page."
        };
      }

      return {
        text: requestedText,
        strategy: "manual",
        pageType: "manual",
        root: null,
        input
      };
    }

    const pageType = detectPageType();
    if (!pageType) {
      return {
        error: "No supported typing prompt layout was detected on this page."
      };
    }

    const ready = await waitForPromptReady(pageType);
    const container = ready.container || locatePromptContainer(pageType);
    console.log("CONTAINER:", container);

    if (!(container instanceof Element)) {
      return {
        error: "No prompt container was detected near the typing input."
      };
    }

    const text = normalizeText(ready.text || extractStructuredText(pageType, container));
    console.log("EXTRACTED TEXT:", text);

    if (!text) {
      return {
        error: "No visible typing prompt was found on this page."
      };
    }

    const input = locateInputField(container);
    if (!input) {
      return {
        error: "No editable input field was detected on this page."
      };
    }

    return {
      text,
      strategy: pageType,
      pageType,
      root: container,
      input
    };
  }

  function getRequestCacheKey(request = {}) {
    const requestedText = getRequestedText(request.customText);
    return requestedText ? `manual:${requestedText}` : "page";
  }

  function resolveTypingContext(request = {}) {
    const key = getRequestCacheKey(request);
    if (pendingContextPromise && pendingContextKey === key) {
      return pendingContextPromise;
    }

    const promise = prepareTypingContext(request).finally(() => {
      if (pendingContextPromise === promise) {
        pendingContextPromise = null;
        pendingContextKey = "";
      }
    });

    pendingContextPromise = promise;
    pendingContextKey = key;
    return promise;
  }

  function getPublicState() {
    return {
      ...state,
      pageTitle: document.title,
      hostname: window.location.hostname,
      preview: state.extractedText.slice(0, 140)
    };
  }

  function setErrorState(message, fallbackText = "") {
    state.status = "error";
    state.message = message;
    state.targetLabel = "";
    state.lastError = message;
    state.extractedText = fallbackText;
    state.progress = 0;
    state.total = fallbackText.length;
    return getPublicState();
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
      state.message = details.reason || "Typing stopped.";
    },
    onError(details) {
      state.status = "error";
      state.lastError = details.error;
      state.message = details.error;
    }
  });

  function typeWithTiming(context, wpm) {
    typer.start({
      element: context.input,
      text: context.text,
      wpm,
      verifyProgress
    });
  }

  async function updateReadyState(request = {}) {
    const fallbackText = getRequestedText(request.customText);
    const context = await resolveTypingContext(request);

    if (context.error) {
      return setErrorState(context.error, fallbackText);
    }

    state.status = "ready";
    state.message = context.strategy === "manual"
      ? `Ready to type ${context.text.length} pasted characters.`
      : `Ready to type ${context.text.length} characters using ${context.pageType}.`;
    state.extractedText = context.text;
    state.strategy = context.strategy;
    state.targetLabel = describeElement(context.input);
    state.progress = 0;
    state.total = context.text.length;
    state.lastError = "";
    return getPublicState();
  }

  async function startTyping(request = {}) {
    if (typer.getState().running) {
      state.message = "Typing is already in progress.";
      return getPublicState();
    }

    const requestedWpm = Math.min(Math.max(Number(request.wpm) || 65, 10), 240);
    state.wpm = requestedWpm;

    const context = await resolveTypingContext(request);
    if (context.error) {
      return setErrorState(context.error, getRequestedText(request.customText));
    }

    state.extractedText = context.text;
    state.strategy = context.strategy;
    state.targetLabel = describeElement(context.input);
    state.progress = 0;
    state.total = context.text.length;
    state.lastError = "";

    try {
      typeWithTiming(context, requestedWpm);
    } catch (error) {
      return setErrorState(error.message || String(error), context.text);
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
        updateReadyState(message || {})
          .then(sendResponse)
          .catch((error) => sendResponse(setErrorState(error.message || String(error))));
      }
      return;
    }

    if (action === "START_TYPING") {
      startTyping(message || {})
        .then(sendResponse)
        .catch((error) => sendResponse(setErrorState(error.message || String(error))));
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
})();
