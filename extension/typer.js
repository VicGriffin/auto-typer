(() => {
  function sleep(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function getKeyValue(character) {
    if (character === "\n") {
      return "Enter";
    }

    if (character === "\t") {
      return "Tab";
    }

    if (character === " ") {
      return " ";
    }

    return character;
  }

  function dispatchKeyboardEvent(element, type, character) {
    const key = getKeyValue(character);
    const event = new KeyboardEvent(type, {
      key,
      code: key === "Enter" ? "Enter" : "",
      bubbles: true,
      cancelable: true
    });
    element.dispatchEvent(event);
  }

  function dispatchInputEvent(element, character, inputType) {
    let event;
    try {
      event = new InputEvent("input", {
        data: character,
        inputType,
        bubbles: true
      });
    } catch (error) {
      event = new Event("input", { bubbles: true });
    }

    element.dispatchEvent(event);
  }

  function isContentEditableElement(element) {
    return Boolean(element && element.isContentEditable);
  }

  function focusEditable(element) {
    if (typeof element.focus === "function") {
      element.focus({ preventScroll: false });
    }
  }

  function insertIntoContentEditable(element, character) {
    const selection = window.getSelection();
    if (!selection) {
      element.textContent = `${element.textContent || ""}${character}`;
      return;
    }

    if (!selection.rangeCount) {
      const range = document.createRange();
      range.selectNodeContents(element);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    const range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(document.createTextNode(character));
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function insertIntoTextField(element, character) {
    const start = typeof element.selectionStart === "number" ? element.selectionStart : element.value.length;
    const end = typeof element.selectionEnd === "number" ? element.selectionEnd : element.value.length;

    if (typeof element.setRangeText === "function") {
      element.setRangeText(character, start, end, "end");
      return;
    }

    element.value = `${element.value.slice(0, start)}${character}${element.value.slice(end)}`;
    const caret = start + character.length;
    if (typeof element.setSelectionRange === "function") {
      element.setSelectionRange(caret, caret);
    }
  }

  function insertCharacter(element, character) {
    if (character === "\n" && element instanceof HTMLInputElement) {
      return;
    }

    if (isContentEditableElement(element)) {
      insertIntoContentEditable(element, character);
      return;
    }

    insertIntoTextField(element, character);
  }

  function getEditableSnapshot(element) {
    if (isContentEditableElement(element)) {
      return element.textContent || "";
    }

    return typeof element.value === "string" ? element.value : "";
  }

  function calculateDelay(wpm) {
    const safeWpm = Math.max(Number(wpm) || 60, 1);
    const charactersPerMinute = safeWpm * 5;
    return 60000 / charactersPerMinute;
  }

  class PageTyper {
    constructor(callbacks = {}) {
      this.callbacks = callbacks;
      this.stopRequested = false;
      this.running = false;
      this.progress = 0;
      this.total = 0;
      this.lastError = "";
    }

    getState() {
      return {
        running: this.running,
        progress: this.progress,
        total: this.total,
        lastError: this.lastError
      };
    }

    start({ element, text, wpm }) {
      if (this.running) {
        throw new Error("Typing is already in progress.");
      }

      if (!element) {
        throw new Error("No editable field was provided.");
      }

      this.running = true;
      this.stopRequested = false;
      this.progress = 0;
      this.total = text.length;
      this.lastError = "";

      if (typeof this.callbacks.onStart === "function") {
        this.callbacks.onStart({
          element,
          text,
          wpm,
          total: this.total
        });
      }

      this.run(element, String(text || ""), Number(wpm) || 60)
        .catch((error) => {
          this.lastError = error.message || String(error);
          if (typeof this.callbacks.onError === "function") {
            this.callbacks.onError({
              error: this.lastError
            });
          }
        })
        .finally(() => {
          this.running = false;
          this.stopRequested = false;
        });
    }

    stop() {
      if (!this.running) {
        return false;
      }

      this.stopRequested = true;
      return true;
    }

    async run(element, text, wpm) {
      focusEditable(element);

      const delay = calculateDelay(wpm);
      const inputType = "insertText";
      const progressStep = Math.max(Math.floor(text.length / 25), 1);

      for (let index = 0; index < text.length; index += 1) {
        if (this.stopRequested) {
          if (typeof this.callbacks.onStop === "function") {
            this.callbacks.onStop({
              typed: index,
              total: text.length
            });
          }
          return;
        }

        const character = text[index];
        const beforeValue = getEditableSnapshot(element);

        dispatchKeyboardEvent(element, "keydown", character);
        insertCharacter(element, character);
        dispatchInputEvent(
          element,
          character === "\n" ? null : character,
          character === "\n" ? "insertLineBreak" : inputType
        );
        dispatchKeyboardEvent(element, "keyup", character);

        const afterValue = getEditableSnapshot(element);
        if (beforeValue === afterValue && character !== "\n") {
          throw new Error("The page rejected typed input for the detected field.");
        }

        this.progress = index + 1;
        if (
          this.progress === this.total ||
          this.progress % progressStep === 0
        ) {
          if (typeof this.callbacks.onProgress === "function") {
            this.callbacks.onProgress({
              typed: this.progress,
              total: this.total
            });
          }
        }

        await sleep(delay);
      }

      element.dispatchEvent(new Event("change", { bubbles: true }));

      if (typeof this.callbacks.onComplete === "function") {
        this.callbacks.onComplete({
          typed: this.total,
          total: this.total
        });
      }
    }
  }

  window.OwnedTypingTyper = {
    PageTyper
  };
})();
