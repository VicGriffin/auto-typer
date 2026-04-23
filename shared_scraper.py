from __future__ import annotations

import ipaddress
import re
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    webdriver = None
    ChromeService = None
    ChromeDriverManager = None


PRESET_SITES = {
    "LiveChat Typing Test": "https://www.livechat.com/typing-speed-test/#/",
    "10FastFingers": "https://10fastfingers.com/typing-test/english",
    "TypingTest.com": "https://www.typingtest.com/",
    "Monkeytype": "https://monkeytype.com/",
    "Custom URL": "",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


class DependencyError(RuntimeError):
    """Raised when a required scraping dependency is missing."""


class ScrapeError(RuntimeError):
    """Raised when a page cannot be scraped into usable typing text."""


@dataclass
class ScrapeResult:
    url: str
    source: str
    text: str
    used_selenium: bool = False

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def characters(self) -> int:
        return len(self.text)


def normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = f"https://{value}"
    return value


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are supported.")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("The URL must include a host name.")

    blocked_hosts = {"localhost", "127.0.0.1", "::1"}
    if host in blocked_hosts or host.endswith(".local"):
        raise ValueError("Local and loopback addresses are not allowed.")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("Private or special-purpose IP addresses are not allowed.")


def calculate_metrics(text: str, duration_minutes: float = 1.0) -> dict[str, float | int]:
    safe_duration = max(float(duration_minutes or 1.0), 0.1)
    words = len(text.split())
    characters = len(text)
    target_wpm = (words / safe_duration) if words else 0.0
    interval_ms = ((safe_duration * 60 * 1000) / characters) if characters else 0.0
    return {
        "words": words,
        "characters": characters,
        "target_wpm": round(target_wpm, 1),
        "interval_ms": round(interval_ms),
    }


def extract_text_from_url(url: str, timeout: int = 10, allow_selenium: bool = True) -> ScrapeResult:
    if requests is None or BeautifulSoup is None:
        raise DependencyError(
            "Scraping needs requests and beautifulsoup4. Install dependencies from requirements.txt first."
        )

    normalized_url = normalize_url(url)
    if not normalized_url:
        raise ValueError("Enter a website URL first.")

    validate_public_url(normalized_url)

    response = requests.get(
        normalized_url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    extracted_text = extract_typing_content(soup, normalized_url).strip()
    used_selenium = False

    if not extracted_text and allow_selenium:
        rendered_html = render_page_with_selenium(normalized_url)
        if rendered_html:
            rendered_soup = BeautifulSoup(rendered_html, "html.parser")
            extracted_text = extract_typing_content(rendered_soup, normalized_url).strip()
            used_selenium = bool(extracted_text)

    if not extracted_text:
        raise ScrapeError(
            "Could not extract typing text from that page. The site may hide the words until you interact with it."
        )

    return ScrapeResult(
        url=normalized_url,
        source=format_source_name(normalized_url),
        text=extracted_text,
        used_selenium=used_selenium,
    )


def extract_typing_content(soup, url: str) -> str:
    url_lower = url.lower()

    if "livechat.com" in url_lower:
        livechat_text = extract_livechat_words(soup.get_text(" ", strip=True))
        if livechat_text:
            return livechat_text

    selectors = [
        ".word",
        ".word.active",
        ".typing-test .word",
        ".typingTest .word",
        ".typing-text",
        ".text-to-type",
        ".test-text",
        ".sentence",
        ".paragraph",
        '[data-testid="word"]',
        ".wordlist span",
        ".letters .letter",
    ]

    for selector in selectors:
        elements = soup.select(selector)
        candidate = join_visible_text(elements)
        if looks_like_typing_text(candidate):
            return candidate

    script_candidate = extract_words_from_scripts(soup)
    if script_candidate:
        return script_candidate

    container_selectors = [
        "main",
        "article",
        ".content",
        ".main-content",
        ".test-wrapper",
        "#root",
        "body",
    ]

    for selector in container_selectors:
        elements = soup.select(selector)
        candidate = clean_text(join_visible_text(elements))
        if looks_like_typing_text(candidate):
            return candidate

    page_text = clean_text(soup.get_text(" ", strip=True))
    if looks_like_typing_text(page_text):
        return " ".join(page_text.split()[:120])

    return ""


def extract_livechat_words(page_text: str) -> str:
    compact = re.sub(r"[^a-z]", "", page_text.lower())
    match = re.search(r"([a-z]{45,})", compact)
    if not match:
        return ""

    chunk = match.group(1)
    words: list[str] = []
    index = 0
    preferred_lengths = [5, 6, 4, 7, 3, 8]

    while index < len(chunk):
        matched = False
        for word_length in preferred_lengths:
            word = chunk[index:index + word_length]
            if len(word) < 3:
                continue

            vowels = sum(1 for char in word if char in "aeiou")
            consonants = sum(1 for char in word if char in "bcdfghjklmnpqrstvwxyz")
            if vowels >= 1 and consonants >= 1:
                words.append(word)
                index += word_length
                matched = True
                break

        if not matched:
            index += 1

    if len(words) >= 10:
        return " ".join(words)
    return ""


def extract_words_from_scripts(soup) -> str:
    script_text = " ".join(script.get_text(" ", strip=True) for script in soup.find_all("script"))
    if not script_text:
        return ""

    patterns = [
        r"\[(?:\s*[\"'][A-Za-z][A-Za-z'-]{1,20}[\"']\s*,){8,}\s*[\"'][A-Za-z][A-Za-z'-]{1,20}[\"']\s*\]",
        r"words?\s*[:=]\s*\[(?:\s*[\"'][A-Za-z][A-Za-z'-]{1,20}[\"']\s*,){8,}\s*[\"'][A-Za-z][A-Za-z'-]{1,20}[\"']\s*\]",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, script_text):
            words = re.findall(r"[\"']([A-Za-z][A-Za-z'-]{1,20})[\"']", match.group(0))
            if len(words) >= 10:
                return " ".join(words)
    return ""


def join_visible_text(elements: Iterable) -> str:
    chunks: list[str] = []
    for element in elements:
        text = element.get_text(" ", strip=True)
        if text:
            chunks.append(text)
    return clean_text(" ".join(chunks))


def clean_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", compact)


def looks_like_typing_text(text: str) -> bool:
    if not text or len(text) < 30:
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'-]{1,}", text)
    unique_words = len({word.lower() for word in words})
    return len(words) >= 8 and unique_words >= 4


def render_page_with_selenium(url: str, timeout: int = 15) -> str:
    if webdriver is None or ChromeService is None or ChromeDriverManager is None:
        return ""

    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        time.sleep(2)
        return driver.page_source
    except Exception:
        return ""
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def format_source_name(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    return host or url
