(() => {
  const elements = {
    domainPill: document.querySelector("#domainPill"),
    pageHost: document.querySelector("#pageHost"),
    customTextInput: document.querySelector("#customTextInput"),
    wpmInput: document.querySelector("#wpmInput"),
    startButton: document.querySelector("#startButton"),
    stopButton: document.querySelector("#stopButton"),
    statusPill: document.querySelector("#statusPill"),
    statusText: document.querySelector("#statusText"),
    targetText: document.querySelector("#targetText"),
    previewText: document.querySelector("#previewText")
  };

  let activeTabId = null;
  let pollTimer = null;
  let lastTransportError = "";
  const manifestContentScripts = chrome.runtime.getManifest().content_scripts || [];
  const contentScriptFiles = manifestContentScripts.flatMap((entry) => entry.js || []);

  function setPill(element, label, tone) {
    element.textContent = label;
    element.classList.remove("error", "busy");

    if (tone === "error") {
      element.classList.add("error");
    } else if (tone === "busy") {
      element.classList.add("busy");
    }
  }

  function getActiveTab() {
    return new Promise((resolve, reject) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(error.message));
          return;
        }

        resolve(tabs[0] || null);
      });
    });
  }

  function isInjectableTab(tab) {
    if (!tab) {
      return false;
    }

    const url = tab.url || tab.pendingUrl || "";
    return /^https?:\/\//i.test(url);
  }

  function injectContentScripts(tabId) {
    return new Promise((resolve, reject) => {
      if (!contentScriptFiles.length) {
        reject(new Error("No content script files are configured in the manifest."));
        return;
      }

      chrome.scripting.executeScript(
        {
          target: { tabId },
          files: contentScriptFiles
        },
        () => {
          const error = chrome.runtime.lastError;
          if (error) {
            reject(new Error(error.message));
            return;
          }

          resolve();
        }
      );
    });
  }

  function sendMessageToActiveTab(payload) {
    return new Promise((resolve, reject) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const queryError = chrome.runtime.lastError;
        if (queryError) {
          reject(new Error(queryError.message));
          return;
        }

        const activeTab = tabs[0] || null;
        if (!activeTab || typeof activeTab.id !== "number") {
          reject(new Error("No active tab found."));
          return;
        }

        activeTabId = activeTab.id;
        console.log("Sending message to tab", {
          tabId: activeTab.id,
          url: activeTab.url || activeTab.pendingUrl || "",
          payload
        });

        chrome.tabs.sendMessage(
          activeTab.id,
          payload,
          (response) => {
            const sendError = chrome.runtime.lastError;
            if (sendError) {
              console.error("sendMessage failed", {
                tabId: activeTab.id,
                payload,
                error: sendError.message
              });
              reject(new Error(sendError.message));
              return;
            }

            console.log("Received response from tab", response);
            resolve({
              tab: activeTab,
              response: response || null
            });
          }
        );
      });
    });
  }

  async function ensureConnection(payload) {
    try {
      return await sendMessageToActiveTab(payload);
    } catch (error) {
      const message = error.message || String(error);
      const activeTab = await getActiveTab();

      if (!activeTab || typeof activeTab.id !== "number") {
        throw error;
      }

      if (!/Receiving end does not exist/i.test(message)) {
        throw error;
      }

      if (!isInjectableTab(activeTab)) {
        throw new Error(
          "This tab does not allow content script injection. Try a normal http or https page."
        );
      }

      console.warn("No receiving end on tab, reinjecting content scripts", {
        tabId: activeTab.id,
        url: activeTab.url || activeTab.pendingUrl || "",
        files: contentScriptFiles
      });

      await injectContentScripts(activeTab.id);
      return sendMessageToActiveTab(payload);
    }
  }

  function normalizeCustomText(text) {
    return String(text || "")
      .replace(/\r/g, "")
      .trim();
  }

  function getCustomText() {
    return normalizeCustomText(elements.customTextInput.value);
  }

  function getStoredSettings() {
    return new Promise((resolve) => {
      chrome.storage.local.get(["wpm", "customText"], (items) => {
        const value = Number(items.wpm);
        resolve({
          wpm: Number.isFinite(value) ? value : 65,
          customText: normalizeCustomText(items.customText)
        });
      });
    });
  }

  function setStoredSettings(nextSettings) {
    chrome.storage.local.set(nextSettings);
  }

  function renderState(tab, state) {
    elements.pageHost.textContent = tab ? (tab.url || tab.pendingUrl || "Unknown tab") : "No active tab";

    if (!tab || !state) {
      setPill(elements.domainPill, "Unavailable", "error");
      setPill(elements.statusPill, "Unavailable", "error");
      elements.statusText.textContent =
        lastTransportError || "The extension could not talk to a content script on this tab.";
      elements.targetText.textContent = "";
      elements.previewText.textContent = "Open an allowed page and reload it after installing the extension.";
      elements.startButton.disabled = true;
      elements.stopButton.disabled = true;
      return;
    }

    setPill(elements.domainPill, "Connected", "default");
    lastTransportError = "";

    const statusTone =
      state.status === "typing" ? "busy" :
      state.status === "error" ? "error" :
      "default";

    setPill(elements.statusPill, state.status || "idle", statusTone);
    elements.statusText.textContent = state.message || "No status reported.";
    elements.targetText.textContent = state.targetLabel ? `Target: ${state.targetLabel}` : "";
    elements.previewText.textContent = state.preview || "No prompt extracted yet.";

    elements.startButton.disabled = state.status === "typing";
    elements.stopButton.disabled = state.status !== "typing";
  }

  async function refreshState() {
    try {
      const tab = await getActiveTab();
      if (!tab || typeof tab.id !== "number") {
        activeTabId = null;
        renderState(null, null);
        return;
      }

      activeTabId = tab.id;
      const result = await ensureConnection({
        action: "GET_STATE",
        customText: getCustomText()
      });
      renderState(result.tab, result.response);
    } catch (error) {
      lastTransportError = error.message || String(error);
      console.error("State refresh failed", error);
      renderState(await getActiveTab().catch(() => null), null);
    }
  }

  async function startTyping() {
    const wpm = Math.min(Math.max(Number(elements.wpmInput.value) || 65, 10), 240);
    elements.wpmInput.value = String(wpm);
    setStoredSettings({
      wpm,
      customText: getCustomText()
    });

    try {
      const handshake = await ensureConnection({ action: "START" });
      console.log("Handshake response", handshake.response);

      const result = await ensureConnection({
        action: "START_TYPING",
        wpm,
        customText: getCustomText()
      });

      renderState(result.tab, result.response);
    } catch (error) {
      lastTransportError = error.message || String(error);
      console.error("Start typing failed", error);
      renderState(await getActiveTab().catch(() => null), null);
    }
  }

  async function stopTyping() {
    try {
      const result = await ensureConnection({
        action: "STOP_TYPING"
      });

      renderState(result.tab, result.response);
    } catch (error) {
      lastTransportError = error.message || String(error);
      console.error("Stop typing failed", error);
      renderState(await getActiveTab().catch(() => null), null);
    }
  }

  async function init() {
    const storedSettings = await getStoredSettings();
    elements.wpmInput.value = String(storedSettings.wpm);
    elements.customTextInput.value = storedSettings.customText;

    elements.wpmInput.addEventListener("change", () => {
      const wpm = Math.min(Math.max(Number(elements.wpmInput.value) || 65, 10), 240);
      elements.wpmInput.value = String(wpm);
      setStoredSettings({ wpm });
    });

    elements.customTextInput.addEventListener("input", () => {
      const customText = getCustomText();
      if (elements.customTextInput.value !== customText) {
        elements.customTextInput.value = customText;
      }

      setStoredSettings({ customText });
      refreshState().catch(() => {});
    });

    elements.startButton.addEventListener("click", startTyping);
    elements.stopButton.addEventListener("click", stopTyping);

    await refreshState();
    pollTimer = window.setInterval(refreshState, 1000);
  }

  window.addEventListener("unload", () => {
    if (pollTimer) {
      window.clearInterval(pollTimer);
    }
  });

  init();
})();
