# Owned Page Typing Assistant

This repository currently contains two related implementations for automating page typing:

- a Chrome/Edge Manifest V3 extension in `extension/`
- a standalone desktop bot in `bot/` built with Playwright and Tkinter

Both implementations aim to:

- detect visible typing prompt text on the current page
- find a usable input, textarea, or contenteditable target
- type at a configurable words-per-minute rate
- allow the run to be stopped partway through

## Project Structure

```text
.
|-- manifest.json
|-- README.md
|-- extension/
|   |-- manifest.json
|   |-- content.js
|   |-- popup.html
|   |-- popup.js
|   |-- scraper.js
|   `-- typer.js
`-- bot/
    |-- browser_controller.py
    |-- main.py
    |-- requirements.txt
    |-- scraper.py
    |-- state_manager.py
    |-- typer.py
    `-- ui.py
```

## Browser Extension

The extension popup lets you:

- inspect the active tab connection state
- paste custom text to type
- set a target WPM
- start and stop typing
- preview the detected prompt text

### Extension Layout

There are two manifest entry points:

- `manifest.json` at the repo root, which points to files inside `extension/`
- `extension/manifest.json`, which uses paths relative to the `extension/` folder itself

That means you can load either:

- the repo root folder
- the `extension` folder

### Current Injection Behavior

The current manifests use `<all_urls>` in both `host_permissions` and `content_scripts.matches`.

In practice, the popup only works on normal `http` and `https` tabs, and `popup.js` will automatically reinject the content scripts if the active tab missed the initial load.

If you want to lock this down before distribution, tighten the manifest matches and `host_permissions` rather than relying on the current broad defaults.

### Prompt Detection

The extension scraper supports three broad page layouts:

- word-based prompts
- letter-based prompts
- paragraph or text-block prompts

If the popup `Paste Text To Type` box contains text, that pasted text takes priority over scraped page content.

### Load The Extension

1. Open Chrome or Edge.
2. Visit `chrome://extensions` or `edge://extensions`.
3. Turn on `Developer mode`.
4. Click `Load unpacked`.
5. Select either the repo root or the `extension` folder.

Chrome and Edge expect a folder here, not an individual manifest file.

### Use The Extension

1. Open a normal `http` or `https` page with a prompt and editable field.
2. Open the extension popup.
3. Optionally paste custom text.
4. Set the target WPM.
5. Click `Start`.
6. Click `Stop` if you want to interrupt the run.

## Standalone Desktop Bot

The `bot/` directory contains a separate desktop workflow with:

- Playwright browser control
- a Tkinter GUI
- prompt detection and input targeting similar to the extension
- optional OS-level typing fallback through PyAutoGUI

### Install Dependencies

From the repository root:

```powershell
pip install -r bot/requirements.txt
python -m playwright install chromium
```

### Run The Desktop Bot

```powershell
python bot/main.py
```

The desktop UI lets you enter:

- a target URL
- a WPM value
- Start and Stop commands

It also shows a live status line and a scrolling run log.

### Optional Browser Attachment

If you already have a Chromium-based browser running with remote debugging enabled, set `BOT_BROWSER_CDP_URL` before launching the bot. `bot/ui.py` passes that value into the run config so the bot can attach over CDP instead of starting a fresh browser.

## Implementation Notes

- `extension/scraper.js` and `bot/scraper.py` use similar strategies for finding prompt containers near editable fields.
- `extension/typer.js` handles in-page typing for the browser extension.
- `bot/typer.py` uses Playwright keyboard input first and can fall back to OS-level keystrokes when enabled.
- `bot/browser_controller.py` launches Chrome by channel when available and falls back to Playwright Chromium if needed.

## Development

There is no build step for the extension.

For normal iteration:

- edit files under `extension/` and reload the unpacked extension
- edit files under `bot/` and rerun `python bot/main.py`

This repository does not currently include automated tests.
