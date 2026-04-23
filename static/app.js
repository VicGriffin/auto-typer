const config = window.appConfig || { presets: {}, defaultText: "" };

const elements = {
  presetSelect: document.querySelector("#presetSelect"),
  urlInput: document.querySelector("#urlInput"),
  scrapeButton: document.querySelector("#scrapeButton"),
  loadDemoButton: document.querySelector("#loadDemoButton"),
  sourceText: document.querySelector("#sourceText"),
  durationInput: document.querySelector("#durationInput"),
  countdownInput: document.querySelector("#countdownInput"),
  pressEnterInput: document.querySelector("#pressEnterInput"),
  playButton: document.querySelector("#playButton"),
  stopButton: document.querySelector("#stopButton"),
  copyButton: document.querySelector("#copyButton"),
  clearButton: document.querySelector("#clearButton"),
  typingPad: document.querySelector("#typingPad"),
  sourcePill: document.querySelector("#sourcePill"),
  wordsValue: document.querySelector("#wordsValue"),
  charactersValue: document.querySelector("#charactersValue"),
  wpmValue: document.querySelector("#wpmValue"),
  intervalValue: document.querySelector("#intervalValue"),
  statusText: document.querySelector("#statusText"),
  statusDot: document.querySelector("#statusDot"),
  progressFill: document.querySelector("#progressFill"),
  activityFeed: document.querySelector("#activityFeed"),
};

const playbackState = {
  active: false,
  cancelled: false,
  timeoutId: null,
  resolveWait: null,
};

function setSourceLabel(label) {
  elements.sourcePill.textContent = label;
}

function setStatus(message, tone = "ready") {
  elements.statusText.textContent = message;
  elements.statusDot.classList.remove("busy", "error");

  if (tone === "busy") {
    elements.statusDot.classList.add("busy");
  } else if (tone === "error") {
    elements.statusDot.classList.add("error");
  }
}

function setProgress(value) {
  const clamped = Math.max(0, Math.min(100, value));
  elements.progressFill.style.width = `${clamped}%`;
}

function logActivity(message) {
  const item = document.createElement("div");
  item.className = "activity-item";

  const stamp = document.createElement("span");
  stamp.className = "activity-time";
  stamp.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  item.append(stamp, document.createTextNode(message));
  elements.activityFeed.prepend(item);

  while (elements.activityFeed.children.length > 8) {
    elements.activityFeed.removeChild(elements.activityFeed.lastChild);
  }
}

function getDurationMinutes() {
  const duration = Number(elements.durationInput.value);
  return Number.isFinite(duration) && duration > 0 ? duration : 1;
}

function getCountdownSeconds() {
  const countdown = Number(elements.countdownInput.value);
  return Number.isFinite(countdown) && countdown > 0 ? Math.round(countdown) : 3;
}

function getMetrics(text) {
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const characters = text.length;
  const duration = getDurationMinutes();
  const targetWpm = words ? (words / duration) : 0;
  const intervalMs = characters ? ((duration * 60 * 1000) / characters) : 0;
  return {
    words,
    characters,
    targetWpm,
    intervalMs,
  };
}

function updateMetrics() {
  const metrics = getMetrics(elements.sourceText.value);
  elements.wordsValue.textContent = String(metrics.words);
  elements.charactersValue.textContent = String(metrics.characters);
  elements.wpmValue.textContent = metrics.targetWpm.toFixed(1);
  elements.intervalValue.textContent = `${Math.round(metrics.intervalMs)} ms`;
}

function syncPresetUrl() {
  const presetUrl = elements.presetSelect.value;
  if (presetUrl) {
    elements.urlInput.value = presetUrl;
  }
}

function populatePresets() {
  const entries = Object.entries(config.presets || {});
  elements.presetSelect.innerHTML = "";

  for (const [label, url] of entries) {
    const option = document.createElement("option");
    option.value = url;
    option.textContent = label;
    elements.presetSelect.append(option);
  }
}

function waitOrCancel(ms) {
  return new Promise((resolve) => {
    playbackState.resolveWait = resolve;
    playbackState.timeoutId = window.setTimeout(() => {
      playbackState.timeoutId = null;
      playbackState.resolveWait = null;
      resolve();
    }, ms);
  });
}

function cancelPendingWait() {
  if (playbackState.timeoutId !== null) {
    window.clearTimeout(playbackState.timeoutId);
    playbackState.timeoutId = null;
  }

  if (playbackState.resolveWait) {
    const resolve = playbackState.resolveWait;
    playbackState.resolveWait = null;
    resolve();
  }
}

function setPlaybackButtons(running) {
  elements.playButton.disabled = running;
  elements.scrapeButton.disabled = running;
}

function stopPlayback(showMessage = true) {
  const wasRunning = playbackState.active;
  playbackState.cancelled = true;
  playbackState.active = false;
  cancelPendingWait();
  setPlaybackButtons(false);

  if (showMessage && wasRunning) {
    setStatus("Typing stopped.", "ready");
    setProgress(0);
    logActivity("Stopped the browser typing playback.");
  }
}

async function startPlayback() {
  const text = elements.sourceText.value;

  if (!text.trim()) {
    setStatus("Add or scrape some text before starting playback.", "error");
    logActivity("Playback could not start because the text workspace is empty.");
    return;
  }

  stopPlayback(false);
  playbackState.active = true;
  playbackState.cancelled = false;
  setPlaybackButtons(true);
  elements.typingPad.value = "";
  elements.typingPad.focus();

  const countdown = getCountdownSeconds();
  for (let remaining = countdown; remaining > 0; remaining -= 1) {
    if (playbackState.cancelled) {
      return;
    }

    setStatus(`Typing starts in ${remaining} second(s). Click into the typing pad if needed.`, "busy");
    setProgress(((countdown - remaining) / countdown) * 15);
    await waitOrCancel(1000);
  }

  if (playbackState.cancelled) {
    return;
  }

  const durationMs = getDurationMinutes() * 60 * 1000;
  const interval = text.length ? (durationMs / text.length) : 0;
  setStatus("Typing in progress...", "busy");
  logActivity(`Started browser playback for ${text.trim().split(/\s+/).length} words.`);

  for (let index = 0; index < text.length; index += 1) {
    if (playbackState.cancelled) {
      return;
    }

    elements.typingPad.value += text[index];
    elements.typingPad.scrollTop = elements.typingPad.scrollHeight;
    setProgress(18 + (((index + 1) / text.length) * 82));
    await waitOrCancel(interval);
  }

  if (!playbackState.cancelled && elements.pressEnterInput.checked) {
    elements.typingPad.value += "\n";
  }

  playbackState.active = false;
  setPlaybackButtons(false);
  setProgress(100);
  setStatus("Typing complete.", "ready");
  logActivity("Browser playback finished successfully.");

  window.setTimeout(() => {
    if (!playbackState.active) {
      setProgress(0);
      setStatus("Ready to edit text, scrape a site, or start browser playback.", "ready");
    }
  }, 1200);
}

async function scrapeText() {
  const url = elements.urlInput.value.trim();
  if (!url) {
    setStatus("Enter a URL before scraping.", "error");
    logActivity("Scrape request skipped because the URL field is empty.");
    return;
  }

  elements.scrapeButton.disabled = true;
  setStatus("Scraping the page for text...", "busy");
  setProgress(18);

  try {
    const response = await fetch("/api/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        duration: getDurationMinutes(),
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Scraping failed.");
    }

    elements.sourceText.value = payload.text;
    setSourceLabel(`Scraped: ${payload.source}`);
    updateMetrics();
    setProgress(100);
    setStatus("Typing text extracted successfully.", "ready");
    logActivity(
      payload.used_selenium
        ? `Scraped ${payload.metrics.words} words from ${payload.source} with Selenium fallback.`
        : `Scraped ${payload.metrics.words} words from ${payload.source}.`
    );

    window.setTimeout(() => setProgress(0), 900);
  } catch (error) {
    setProgress(0);
    setStatus(error.message, "error");
    logActivity(`Scraping failed: ${error.message}`);
  } finally {
    elements.scrapeButton.disabled = playbackState.active;
  }
}

async function copyText() {
  const text = elements.sourceText.value;
  if (!text.trim()) {
    setStatus("There is no text to copy yet.", "error");
    logActivity("Copy skipped because the text workspace is empty.");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setStatus("Text copied to the clipboard.", "ready");
    logActivity("Copied the current workspace text.");
  } catch (error) {
    setStatus("Clipboard access was blocked by the browser.", "error");
    logActivity(`Clipboard copy failed: ${error.message}`);
  }
}

function clearWorkspace() {
  stopPlayback(false);
  elements.sourceText.value = "";
  elements.typingPad.value = "";
  setSourceLabel("Manual input");
  updateMetrics();
  setProgress(0);
  setStatus("Text workspace cleared.", "ready");
  logActivity("Cleared the source text and typing pad.");
}

function loadDemoText() {
  stopPlayback(false);
  elements.sourceText.value = config.defaultText || "";
  elements.typingPad.value = "";
  setSourceLabel("Demo text");
  updateMetrics();
  setStatus("Loaded the built-in demo text.", "ready");
  logActivity("Loaded the demo text into the workspace.");
}

function bindEvents() {
  elements.presetSelect.addEventListener("change", syncPresetUrl);
  elements.sourceText.addEventListener("input", updateMetrics);
  elements.durationInput.addEventListener("input", updateMetrics);
  elements.scrapeButton.addEventListener("click", scrapeText);
  elements.loadDemoButton.addEventListener("click", loadDemoText);
  elements.playButton.addEventListener("click", startPlayback);
  elements.stopButton.addEventListener("click", () => stopPlayback(true));
  elements.copyButton.addEventListener("click", copyText);
  elements.clearButton.addEventListener("click", clearWorkspace);
}

function init() {
  populatePresets();
  syncPresetUrl();
  elements.sourceText.value = config.defaultText || "";
  updateMetrics();
  setSourceLabel("Demo text");
  setStatus("Ready to edit text, scrape a site, or start browser playback.", "ready");
  logActivity("Web interface loaded.");
  bindEvents();
}

init();
