# Owned Page Typing Assistant

This project is a Chrome/Edge Manifest V3 extension that:

- extracts visible typing text from the current webpage
- finds an editable field on the same page
- types the extracted text into that field
- runs only on an explicit allowlist of domains you control

It does not include anti-detection logic, browser-security bypasses, or support for unapproved third-party platforms.

## Structure

```text
extension/
  manifest.json
  content.js
  scraper.js
  typer.js
  popup.html
  popup.js
```

## Allowed Domains

For debugging injection, both manifests currently inject the content script on `<all_urls>`.

Typing is still gated in `content.js` by `ALLOWED_HOSTS`.

Default entries:

- `http://localhost/*`
- `http://127.0.0.1/*`
- `https://mydomain.com/*`
- `https://*.mydomain.com/*`

Update `ALLOWED_HOSTS` before loading the extension if your owned domain is different.

## Load The Extension

1. Open Chrome or Edge.
2. Go to the extensions page:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
3. Turn on `Developer mode`.
4. Click `Load unpacked`.
5. Select either:
   - the repo root folder, if you want Chrome to use the top-level `manifest.json`
   - the `extension` folder, if you want Chrome to use `extension/manifest.json`

Important: Chrome's `Load unpacked` dialog expects a folder, not a single file. If you do not see a `.crx` or `.js` file to click, that is normal; choose the folder and confirm.

## Use It

1. Open an allowed page that contains:
   - visible typing text on the page
   - an editable input, textarea, or contenteditable field
2. Open the extension popup.
3. Set the target WPM.
4. Click `Start`.
5. Click `Stop` to interrupt typing.

The popup shows:

- whether the current page is allowed
- current typing status
- the detected target field
- a preview of the extracted prompt

## Implementation Notes

- `scraper.js` extracts prompt text from visible word layouts, letter layouts, and paragraph-like blocks.
- `typer.js` dispatches `keydown`, `input`, and `keyup` events while inserting characters into the detected field.
- `content.js` connects extraction, target detection, and typing control for the current page.
- `popup.js` provides the extension UI and sends start/stop commands to the active allowed tab.

## Development

There is no build step and no external runtime dependency. Edit the files in `extension` and reload the unpacked extension from the browser extensions page.
