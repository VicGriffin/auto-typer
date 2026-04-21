import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import re

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    webdriver = None
    ChromeService = None
    By = None
    WebDriverException = None
    ChromeDriverManager = None


class OverlayTyperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Overlay Typer Bot")
        self.root.geometry("500x650+80+80")
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.92)
        self.root.resizable(False, False)

        self.stop_event = threading.Event()
        self.typing_thread = None
        self.scanning_thread = None
        self.last_content = ""
        self.realtime_scanning = False

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="Overlay Typer Bot", font=("Segoe UI", 14, "bold"))
        title.pack(anchor="w")

        info = "Paste or type your message below, set how long it should take to type, then click 'Start Now'."
        ttk.Label(frame, text=info, wraplength=390, foreground="#555").pack(anchor="w", pady=(6, 10))

        # URL input section
        url_frame = ttk.Frame(frame)
        url_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(url_frame, text="Or scrape from website:").pack(anchor="w")

        # Preset URLs dropdown
        preset_frame = ttk.Frame(url_frame)
        preset_frame.pack(fill="x", pady=(2, 2))

        self.preset_var = tk.StringVar()
        presets = {
            "LiveChat Typing Test": "https://www.livechat.com/typing-speed-test/#/",
            "10FastFingers": "https://10fastfingers.com/typing-test/english",
            "TypingTest.com": "https://www.typingtest.com/",
            "Custom URL": ""
        }

        self.preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var, values=list(presets.keys()), state="readonly")
        self.preset_combo.pack(side="left", fill="x", expand=True)
        self.preset_combo.set("LiveChat Typing Test")

        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(preset_frame, textvariable=self.url_var, width=30)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.url_entry.insert(0, presets["LiveChat Typing Test"])

        # Update URL when preset changes
        self.preset_combo.bind('<<ComboboxSelected>>', lambda e: self.update_url_from_preset(presets))

        self.text_widget = tk.Text(frame, width=56, height=14, wrap="word", font=("Segoe UI", 11))
        self.text_widget.pack(fill="both", expand=True)

        duration_frame = ttk.Frame(frame)
        duration_frame.pack(fill="x", pady=(12, 0))

        ttk.Label(duration_frame, text="Finish typing in:").pack(side="left")
        self.duration_var = tk.DoubleVar(value=1.0)
        duration_spin = ttk.Spinbox(
            duration_frame,
            from_=0.1,
            to=10.0,
            increment=0.1,
            textvariable=self.duration_var,
            width=8,
        )
        duration_spin.pack(side="left", padx=(8, 2))
        ttk.Label(duration_frame, text="minutes").pack(side="left")

        self.enter_var = tk.BooleanVar(value=True)
        self.enter_check = ttk.Checkbutton(
            frame,
            text="Press Enter after typing",
            variable=self.enter_var,
        )
        self.enter_check.pack(anchor="w", pady=(10, 0))

        # Real-time scanning toggle
        self.realtime_var = tk.BooleanVar(value=False)
        self.realtime_check = ttk.Checkbutton(
            frame,
            text="Real-time scanning (auto-detect new words)",
            variable=self.realtime_var,
            command=self.toggle_realtime_scanning,
        )
        self.realtime_check.pack(anchor="w", pady=(5, 0))

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(12, 0))

        self.scrape_button = ttk.Button(button_frame, text="Scrape & Type", command=self.scrape_and_type)
        self.scrape_button.pack(side="left", expand=True, fill="x", padx=(0, 2))

        self.type_button = ttk.Button(button_frame, text="Start Now", command=self.on_type)
        self.type_button.pack(side="left", expand=True, fill="x", padx=(2, 2))

        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_typing)
        self.stop_button.pack(side="left", expand=True, fill="x", padx=(2, 0))

        lower_frame = ttk.Frame(frame)
        lower_frame.pack(fill="x", pady=(12, 0))

        self.topmost_var = tk.BooleanVar(value=True)
        self.topmost_button = ttk.Checkbutton(
            lower_frame,
            text="Always on top",
            variable=self.topmost_var,
            command=self.toggle_topmost,
        )
        self.topmost_button.pack(side="left")

        clear_button = ttk.Button(lower_frame, text="Clear", command=self.clear_text)
        clear_button.pack(side="right")

        self.status_label = ttk.Label(frame, text="", foreground="#ff6b00", font=("Segoe UI", 11, "bold"))
        self.status_label.pack(anchor="w", pady=(10, 0))

        hint = "Step 1: Click 'Start Now'\nStep 2: Click your target input field during countdown\nStep 3: Typing begins automatically"
        ttk.Label(frame, text=hint, foreground="#888", wraplength=390, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))
    def update_url_from_preset(self, presets):
        selected = self.preset_var.get()
        if selected in presets:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, presets[selected])
    def clear_text(self):
        self.text_widget.delete("1.0", "end")

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())

    def toggle_realtime_scanning(self):
        if self.realtime_var.get():
            self.start_realtime_scanning()
        else:
            self.stop_realtime_scanning()

    def start_realtime_scanning(self):
        if self.scanning_thread and self.scanning_thread.is_alive():
            return

        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a website URL to scan.")
            self.realtime_var.set(False)
            return

        self.realtime_scanning = True
        self.last_content = ""
        self.scanning_thread = threading.Thread(
            target=self.realtime_scan_loop,
            daemon=True,
        )
        self.scanning_thread.start()
        self.status_label.config(text="Real-time scanning active...")

    def stop_realtime_scanning(self):
        self.realtime_scanning = False
        if self.scanning_thread and self.scanning_thread.is_alive():
            self.scanning_thread.join(timeout=1)
        self.status_label.config(text="Real-time scanning stopped.")

    def realtime_scan_loop(self):
        url = self.url_var.get().strip()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        while self.realtime_scanning and not self.stop_event.is_set():
            try:
                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')
                current_content = self.extract_typing_content(soup, url)

                if not current_content and webdriver is not None:
                    rendered_html = self.render_page_with_selenium(url)
                    if rendered_html:
                        current_content = self.extract_typing_content(BeautifulSoup(rendered_html, 'html.parser'), url)

                if current_content and current_content != self.last_content:
                    # New content detected!
                    new_words = self.get_new_words(current_content, self.last_content)
                    if new_words.strip():
                        self.root.after(0, lambda: self.handle_new_content(new_words))
                        self.last_content = current_content

                time.sleep(2)  # Scan every 2 seconds

            except Exception as e:
                # Silently handle errors during scanning to avoid spam
                time.sleep(5)  # Wait longer on error

    def extract_typing_content(self, soup, url):
        """Extract typing content from soup - shared logic with scrape_and_type"""
        text_content = ""

        # Specific handling for LiveChat typing test
        if 'livechat.com' in url.lower():
            page_text = soup.get_text()
            import re
            concatenated_pattern = r'([a-z]{6,}[a-z]{5,}[a-z]{4,}[a-z]{5,}[a-z]{6,}[a-z]{3,}[a-z]{5,}[a-z]{5,}[a-z]{4,}[a-z]{7,}[a-z]{4,}[a-z]{6,}[a-z]{6,}[a-z]{6,}[a-z]{4,})'
            match = re.search(concatenated_pattern, page_text.lower())
            if match:
                concatenated_text = match.group(1)
                words = []
                i = 0
                while i < len(concatenated_text):
                    for word_len in [6, 5, 4, 7, 8, 3]:
                        if i + word_len <= len(concatenated_text):
                            potential_word = concatenated_text[i:i + word_len]
                            consonants = sum(1 for c in potential_word if c in 'bcdfghjklmnpqrstvwxyz')
                            vowels = sum(1 for c in potential_word if c in 'aeiou')
                            if 1 <= vowels <= word_len - 1 and consonants >= 1:
                                words.append(potential_word)
                                i += word_len
                                break
                    else:
                        i += 1
                if len(words) >= 10:
                    text_content = ' '.join(words)

        if not text_content:
            specific_selectors = [
                '.word', '.words-wrapper .word', '.typing-test .word',
                '.typing-test-text', '.test-text', '.letter', '.char',
                '.typing-text', '.text-to-type', '.sentence', '.paragraph',
                '.content', '.main-content', 'article', '.post-content'
            ]

            for selector in specific_selectors:
                elements = soup.select(selector)
                if elements:
                    words = []
                    for elem in elements:
                        text = elem.get_text().strip()
                        if text and len(text) > 2:
                            words.append(text)
                    if words:
                        text_content = ' '.join(words)
                        if len(text_content) > 100:
                            break

        return text_content.strip()

    def render_page_with_selenium(self, url, timeout=15):
        if webdriver is None or ChromeService is None or ChromeDriverManager is None:
            return ""

        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")

            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

            driver.get(url)
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                WebDriverWait(driver, timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                pass

            # Give the page a little extra time to render dynamic typing content
            time.sleep(2)
            rendered_html = driver.page_source
            return rendered_html
        except Exception:
            return ""
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def get_new_words(self, current_content, last_content):
        """Extract only the new words that appeared since last scan"""
        if not last_content:
            return current_content

        current_words = current_content.split()
        last_words = last_content.split()

        # Find where the content diverged
        min_len = min(len(current_words), len(last_words))
        divergence_point = 0

        for i in range(min_len):
            if current_words[i] != last_words[i]:
                divergence_point = i
                break
        else:
            divergence_point = min_len

        # Return new words from divergence point
        new_words = current_words[divergence_point:]
        return ' '.join(new_words)

    def handle_new_content(self, new_words):
        """Handle newly detected content by updating text and starting typing"""
        if not new_words.strip():
            return

        # Update the text widget with new content
        current_text = self.text_widget.get("1.0", "end").strip()
        if current_text:
            # Append new words
            self.text_widget.insert("end", " " + new_words)
        else:
            # Set as new content
            self.text_widget.delete("1.0", "end")
            self.text_widget.insert("1.0", new_words)

        # Auto-start typing if not already typing
        if not (self.typing_thread and self.typing_thread.is_alive()):
            self.status_label.config(text="New words detected! Starting countdown...")
            self.root.update()
            time.sleep(1)
            self.on_type()

    def stop_typing(self):
        self.stop_event.set()
        self.stop_realtime_scanning()  # Also stop scanning when stopping typing
        self.type_button.config(state="normal")
        self.status_label.config(text="")
        if self.typing_thread and self.typing_thread.is_alive():
            messagebox.showinfo("Stopped", "Typing and scanning have been stopped.")

    def scrape_and_type(self):
        if requests is None or BeautifulSoup is None:
            messagebox.showerror(
                "Missing Dependencies",
                "requests and beautifulsoup4 are required for web scraping.\nInstall with: python -m pip install requests beautifulsoup4",
            )
            return

        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a website URL to scrape from.")
            return

        if self.typing_thread and self.typing_thread.is_alive():
            messagebox.showwarning("Already typing", "Typing is already in progress.")
            return

        self.status_label.config(text="Scraping website...")
        self.root.update()

        try:
            # Scrape the website
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Use shared extraction logic
            text_content = self.extract_typing_content(soup, url)

            # Try Selenium when the site is dynamic and no text was found
            if not text_content and webdriver is not None:
                self.status_label.config(text="Rendering dynamic page with browser...")
                self.root.update()
                rendered_html = self.render_page_with_selenium(url)
                if rendered_html:
                    soup = BeautifulSoup(rendered_html, 'html.parser')
                    text_content = self.extract_typing_content(soup, url)

            text_content = text_content.strip()
            if not text_content:
                messagebox.showerror(
                    "No typing text found",
                    "Could not extract typing test words from the website. The site may use JavaScript to load content dynamically.",
                )
                self.status_label.config(text="")
                return

            # Put the scraped text in the text widget
            self.text_widget.delete("1.0", "end")
            self.text_widget.insert("1.0", text_content)
            self.last_content = text_content

            self.status_label.config(text="Text scraped! Starting countdown...")
            self.root.update()
            time.sleep(1)

            # Start typing
            self.on_type()

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Scraping error", f"Failed to scrape website: {e}")
            self.status_label.config(text="")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
            self.status_label.config(text="")

    def on_type(self, press_enter=None):
        if pyautogui is None:
            messagebox.showerror(
                "Missing Dependency",
                "pyautogui is required. Install it with: python -m pip install pyautogui",
            )
            return

        if press_enter is None:
            press_enter = self.enter_var.get()

        text = self.text_widget.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No text", "Please enter the message you want to type.")
            return

        if self.typing_thread and self.typing_thread.is_alive():
            messagebox.showwarning("Already typing", "Typing is already in progress.")
            return

        self.stop_event.clear()
        duration = float(self.duration_var.get())
        self.type_button.config(state="disabled")
        self.typing_thread = threading.Thread(
            target=self.type_text,
            args=(text, duration, press_enter),
            daemon=True,
        )
        self.typing_thread.start()

    def type_text(self, text: str, duration: float, press_enter: bool):
        countdown = 3
        while countdown > 0 and not self.stop_event.is_set():
            self.status_label.config(text=f"Typing starts in {countdown}... (Click your target field now)")
            self.root.update()
            time.sleep(1)
            countdown -= 1

        if self.stop_event.is_set():
            self.status_label.config(text="")
            self.type_button.config(state="normal")
            return

        self.status_label.config(text="Typing...")
        self.root.update()

        pyautogui.FAILSAFE = False
        try:
            char_count = len(text)
            if char_count == 0:
                self.type_button.config(state="normal")
                self.status_label.config(text="")
                return
            duration_seconds = duration * 60
            interval = duration_seconds / char_count
            for char in text:
                if self.stop_event.is_set():
                    self.type_button.config(state="normal")
                    self.status_label.config(text="")
                    return
                pyautogui.write(char, interval=interval)
            if press_enter and not self.stop_event.is_set():
                pyautogui.press("enter")
            self.status_label.config(text="Done!")
            time.sleep(1)
            self.status_label.config(text="")
        except Exception as exc:
            messagebox.showerror("Typing error", f"Unable to type text: {exc}")
            self.status_label.config(text="Error!")
        finally:
            self.type_button.config(state="normal")


def main():
    root = tk.Tk()
    app = OverlayTyperApp(root)

    def on_closing():
        app.stop_realtime_scanning()
        app.stop_typing()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
