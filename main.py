import re
import threading
import time
import tkinter as tk
import json
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.parse import urlparse


class ToastNotification:
    def __init__(self, parent, message, toast_type="info", duration=3000):
        self.parent = parent
        self.message = message
        self.toast_type = toast_type
        self.duration = duration
        self.alpha = 0.0
        
        self.toast = tk.Toplevel(parent)
        self.toast.withdraw()
        self.toast.overrideredirect(True)
        self.toast.attributes("-topmost", True)
        self.toast.attributes("-alpha", 0.0)
        
        # Get theme colors from parent if available
        if hasattr(parent, 'palette'):
            palette = parent.palette
        else:
            palette = {
                "bg": "#ffffff",
                "text": "#333333",
                "success": "#28a745",
                "warning": "#ffc107",
                "danger": "#dc3545",
                "accent": "#007bff"
            }
        
        # Set colors based on toast type
        bg_colors = {
            "info": palette["accent"],
            "success": palette["success"],
            "warning": palette["warning"],
            "error": palette["danger"]
        }
        
        bg_color = bg_colors.get(toast_type, palette["accent"])
        
        self.toast.configure(bg=bg_color)
        
        # Create toast content
        frame = tk.Frame(self.toast, bg=bg_color, padx=16, pady=12)
        frame.pack()
        
        label = tk.Label(
            frame,
            text=message,
            bg=bg_color,
            fg="white",
            font=("Segoe UI", 10),
            wraplength=300
        )
        label.pack()
        
        # Position toast at top-right of parent
        self.update_position()
        self.toast.deiconify()
        
        # Animate in
        self.fade_in()
        
        # Auto-close after duration
        self.toast.after(duration - 500, self.fade_out)
        self.toast.after(duration, self.close)
    
    def update_position(self):
        self.toast.update_idletasks()
        x = self.parent.winfo_rootx() + self.parent.winfo_width() - 320
        y = self.parent.winfo_rooty() + 80
        self.toast.geometry(f"+{x}+{y}")
    
    def fade_in(self):
        """Fade in animation"""
        if self.alpha < 0.9:
            self.alpha += 0.1
            self.toast.attributes("-alpha", self.alpha)
            self.toast.after(30, self.fade_in)
        else:
            self.toast.attributes("-alpha", 0.9)
    
    def fade_out(self):
        """Fade out animation"""
        if self.alpha > 0.0:
            self.alpha -= 0.1
            self.toast.attributes("-alpha", self.alpha)
            self.toast.after(30, self.fade_out)
        else:
            self.toast.attributes("-alpha", 0.0)
    
    def close(self):
        self.toast.destroy()

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
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    webdriver = None
    ChromeService = None
    ChromeDriverManager = None


class OverlayTyperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Overlay Typer Bot")
        self.root.geometry("1120x780+70+50")
        self.root.minsize(980, 700)
        self.root.attributes("-topmost", True)

        self.presets = {
            "LiveChat Typing Test": "https://www.livechat.com/typing-speed-test/#/",
            "10FastFingers": "https://10fastfingers.com/typing-test/english",
            "TypingTest.com": "https://www.typingtest.com/",
            "Monkeytype": "https://monkeytype.com/",
            "Custom URL": "",
        }

        self.dark_mode = tk.BooleanVar(value=False)
        self.settings_file = Path(__file__).parent / "settings.json"
        
        self.load_settings()
        self.setup_theme()
        
        self.root.configure(bg=self.palette["bg"])
        
        self.stop_event = threading.Event()
        self.typing_thread = None
        self.scanning_thread = None
        self.realtime_scanning = False
        self.is_typing = False
        self.is_scraping = False
        self.last_content = ""

        self.status_var = tk.StringVar(value="Ready to paste text, scrape a site, or start typing.")
        self.badge_var = tk.StringVar(value="Idle")
        self.source_var = tk.StringVar(value="Manual input")
        self.words_var = tk.StringVar(value="0")
        self.characters_var = tk.StringVar(value="0")
        self.wpm_var = tk.StringVar(value="0 wpm")
        self.interval_var = tk.StringVar(value="0 ms")
        self.progress_var = tk.DoubleVar(value=0)

        self.preset_var = tk.StringVar(value="LiveChat Typing Test")
        self.url_var = tk.StringVar(value=self.presets["LiveChat Typing Test"])
        self.duration_var = tk.DoubleVar(value=1.0)
        self.countdown_var = tk.IntVar(value=3)
        self.enter_var = tk.BooleanVar(value=True)
        self.topmost_var = tk.BooleanVar(value=True)

        self.style = ttk.Style()
        self.configure_styles()
        self.create_widgets()
        self.bind_events()
        self.update_metrics()
        self.refresh_action_buttons()

    def setup_theme(self):
        if self.dark_mode.get():
            self.palette = {
                "bg": "#1a1a1a",
                "card": "#2d2d2d",
                "card_alt": "#3a3a3a",
                "border": "#404040",
                "text": "#ffffff",
                "muted": "#b0b0b0",
                "accent": "#4a9eff",
                "accent_hover": "#3a8eef",
                "accent_soft": "#1e3a5f",
                "success": "#28a745",
                "warning": "#ffc107",
                "danger": "#dc3545",
                "surface": "#2a2a2a",
            }
        else:
            self.palette = {
                "bg": "#f4f7fb",
                "card": "#ffffff",
                "card_alt": "#eef3fb",
                "border": "#dce5f2",
                "text": "#152033",
                "muted": "#5d6b82",
                "accent": "#1d6fdc",
                "accent_hover": "#1559b2",
                "accent_soft": "#dcebff",
                "success": "#1f9d68",
                "warning": "#d67b18",
                "danger": "#c44c4c",
                "surface": "#f9fbff",
            }
    
    def load_settings(self):
        try:
            if self.settings_file.exists():
                settings = json.loads(self.settings_file.read_text())
                self.dark_mode.set(settings.get("dark_mode", False))
                self.preset_var.set(settings.get("preset", "LiveChat Typing Test"))
                self.duration_var.set(settings.get("duration", 1.0))
                self.countdown_var.set(settings.get("countdown", 3))
                self.enter_var.set(settings.get("press_enter", True))
                self.topmost_var.set(settings.get("topmost", True))
        except Exception:
            pass
    
    def save_settings(self):
        try:
            settings = {
                "dark_mode": self.dark_mode.get(),
                "preset": self.preset_var.get(),
                "duration": self.duration_var.get(),
                "countdown": self.countdown_var.get(),
                "press_enter": self.enter_var.get(),
                "topmost": self.topmost_var.get(),
            }
            self.settings_file.write_text(json.dumps(settings, indent=2))
        except Exception:
            pass
    
    def toggle_theme(self):
        self.setup_theme()
        self.root.configure(bg=self.palette["bg"])
        self.configure_styles()
        self.apply_theme_to_widgets()
        self.save_settings()
    
    def apply_theme_to_widgets(self):
        if hasattr(self, 'text_widget'):
            self.text_widget.configure(bg=self.palette["card"], fg=self.palette["text"], insertbackground=self.palette["accent"])
        if hasattr(self, 'activity_text'):
            self.activity_text.configure(bg=self.palette["card"], fg=self.palette["text"])
        
        for widget in self.root.winfo_children():
            self.update_widget_theme(widget)
    
    def show_toast(self, message, toast_type="info", duration=3000):
        """Show a toast notification"""
        try:
            ToastNotification(self.root, message, toast_type, duration)
        except Exception:
            # Fallback to activity log if toast fails
            self.log_event(f"Toast ({toast_type}): {message}")
    
    def show_success_toast(self, message):
        """Show success toast notification"""
        self.show_toast(message, "success")
    
    def show_error_toast(self, message):
        """Show error toast notification"""
        self.show_toast(message, "error")
    
    def show_warning_toast(self, message):
        """Show warning toast notification"""
        self.show_toast(message, "warning")
    
    def update_widget_theme(self, widget):
        try:
            if isinstance(widget, ttk.Frame):
                widget.configure(style="App.TFrame")
            for child in widget.winfo_children():
                self.update_widget_theme(child)
        except:
            pass

    def configure_styles(self):
        self.style.theme_use("clam")
        self.style.configure("App.TFrame", background=self.palette["bg"])
        self.style.configure(
            "Card.TFrame",
            background=self.palette["card"],
            bordercolor=self.palette["border"],
            relief="solid",
            borderwidth=1,
        )
        self.style.configure(
            "SoftCard.TFrame",
            background=self.palette["card_alt"],
            bordercolor=self.palette["border"],
            relief="solid",
            borderwidth=1,
        )
        self.style.configure("Header.TLabel", background=self.palette["bg"], foreground=self.palette["text"], font=("Segoe UI Semibold", 25))
        self.style.configure("Subheader.TLabel", background=self.palette["bg"], foreground=self.palette["muted"], font=("Segoe UI", 11))
        self.style.configure("CardTitle.TLabel", background=self.palette["card"], foreground=self.palette["text"], font=("Segoe UI Semibold", 13))
        self.style.configure("CardBody.TLabel", background=self.palette["card"], foreground=self.palette["muted"], font=("Segoe UI", 10))
        self.style.configure("SoftTitle.TLabel", background=self.palette["card_alt"], foreground=self.palette["text"], font=("Segoe UI Semibold", 12))
        self.style.configure("SoftBody.TLabel", background=self.palette["card_alt"], foreground=self.palette["muted"], font=("Segoe UI", 10))
        self.style.configure("Badge.TLabel", background=self.palette["accent_soft"], foreground=self.palette["accent"], font=("Segoe UI Semibold", 10), padding=(14, 6))
        self.style.configure("MetricValue.TLabel", background=self.palette["card_alt"], foreground=self.palette["text"], font=("Segoe UI Semibold", 18))
        self.style.configure("MetricLabel.TLabel", background=self.palette["card_alt"], foreground=self.palette["muted"], font=("Segoe UI", 10))
        self.style.configure("Status.TLabel", background=self.palette["card"], foreground=self.palette["text"], font=("Segoe UI", 10))
        self.style.configure("Muted.TCheckbutton", background=self.palette["card"], foreground=self.palette["text"], font=("Segoe UI", 10))
        self.style.map("Muted.TCheckbutton", background=[("active", self.palette["card"])])
        self.style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(12, 9), background=self.palette["accent"], foreground="#ffffff", borderwidth=0)
        self.style.map("Accent.TButton", background=[("active", self.palette["accent_hover"])])
        self.style.configure("Secondary.TButton", font=("Segoe UI Semibold", 10), padding=(12, 9), background="#edf4ff", foreground=self.palette["accent"], borderwidth=0)
        self.style.map("Secondary.TButton", background=[("active", "#dbe9ff")])
        self.style.configure("Ghost.TButton", font=("Segoe UI", 10), padding=(10, 8), background=self.palette["surface"], foreground=self.palette["text"], borderwidth=0)
        self.style.map("Ghost.TButton", background=[("active", "#eef4fc")])
        self.style.configure("Danger.TButton", font=("Segoe UI Semibold", 10), padding=(12, 9), background="#ffe8e8", foreground=self.palette["danger"], borderwidth=0)
        self.style.map("Danger.TButton", background=[("active", "#ffd5d5")])
        self.style.configure("TEntry", fieldbackground=self.palette["card"], foreground=self.palette["text"], bordercolor=self.palette["border"], lightcolor=self.palette["border"], darkcolor=self.palette["border"], padding=7)
        self.style.configure("TCombobox", fieldbackground=self.palette["card"], foreground=self.palette["text"], bordercolor=self.palette["border"], lightcolor=self.palette["border"], darkcolor=self.palette["border"], padding=6)
        self.style.configure("TSpinbox", fieldbackground=self.palette["card"], foreground=self.palette["text"], bordercolor=self.palette["border"], lightcolor=self.palette["border"], darkcolor=self.palette["border"], padding=6)
        self.style.configure("Modern.Horizontal.TProgressbar", troughcolor=self.palette["border"], background=self.palette["accent"], bordercolor=self.palette["border"], lightcolor=self.palette["accent"], darkcolor=self.palette["accent"])

    def create_widgets(self):
        container = ttk.Frame(self.root, style="App.TFrame", padding=22)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, style="App.TFrame")
        header.pack(fill="x")

        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        
        title_frame = ttk.Frame(title_block, style="App.TFrame")
        title_frame.pack(anchor="w")
        ttk.Label(title_frame, text="Overlay Typer Bot", style="Header.TLabel").pack(side="left", anchor="w")
        
        theme_button = ttk.Button(title_frame, text="🌙" if not self.dark_mode.get() else "☀️", command=self.toggle_theme, style="Ghost.TButton", width=3)
        theme_button.pack(side="right", padx=(10, 0))
        
        ttk.Label(
            title_block,
            text="A cleaner desktop workspace for manual typing, smart scraping, and live typing-test automation.",
            style="Subheader.TLabel",
            wraplength=720,
        ).pack(anchor="w", pady=(4, 0))

        hero_badge = ttk.Label(header, textvariable=self.badge_var, style="Badge.TLabel")
        hero_badge.pack(side="right", padx=(18, 0), pady=(8, 0))

        body = ttk.Frame(container, style="App.TFrame")
        body.pack(fill="both", expand=True, pady=(18, 0))
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        self.workspace_card = ttk.Frame(body, style="Card.TFrame", padding=18)
        self.workspace_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.sidebar = ttk.Frame(body, style="App.TFrame")
        self.sidebar.grid(row=0, column=1, sticky="nsew")
        self.sidebar.columnconfigure(0, weight=1)

        self.build_workspace_card()
        self.build_sidebar()
        self.build_activity_card(container)

    def build_workspace_card(self):
        self.workspace_card.columnconfigure(0, weight=1)
        self.workspace_card.rowconfigure(2, weight=1)

        header_row = ttk.Frame(self.workspace_card, style="Card.TFrame")
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.columnconfigure(0, weight=1)

        ttk.Label(header_row, text="Typing Workspace", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header_row,
            text="Paste text, scrape a site, or build your typing payload from a local file.",
            style="CardBody.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        source_badge = ttk.Label(
            header_row,
            textvariable=self.source_var,
            style="Badge.TLabel",
        )
        source_badge.grid(row=0, column=1, rowspan=2, sticky="e")

        toolbar = ttk.Frame(self.workspace_card, style="Card.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(16, 12))
        for column in range(5):
            toolbar.columnconfigure(column, weight=1)

        ttk.Button(toolbar, text="Paste", command=self.paste_from_clipboard, style="Ghost.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(toolbar, text="Copy", command=self.copy_text, style="Ghost.TButton").grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(toolbar, text="Load File", command=self.load_text_file, style="Ghost.TButton").grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(toolbar, text="Save Text", command=self.save_text_file, style="Ghost.TButton").grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(toolbar, text="Clear", command=self.clear_text, style="Ghost.TButton").grid(row=0, column=4, sticky="ew", padx=(8, 0))

        self.text_widget = scrolledtext.ScrolledText(
            self.workspace_card,
            wrap="word",
            undo=True,
            font=("Consolas", 11),
            bg=self.palette["card"],
            fg=self.palette["text"],
            insertbackground=self.palette["accent"],
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=16,
            height=20,
        )
        self.text_widget.grid(row=2, column=0, sticky="nsew")
        self.text_widget.focus_set()

        footer_row = ttk.Frame(self.workspace_card, style="Card.TFrame")
        footer_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        footer_row.columnconfigure(0, weight=1)

        ttk.Label(
            footer_row,
            text="Tip: for typing tests, scrape the page first so the bot uses the freshest words on screen.",
            style="CardBody.TLabel",
            wraplength=640,
        ).grid(row=0, column=0, sticky="w")

        self.workspace_stats_label = ttk.Label(
            footer_row,
            text="0 words - 0 characters",
            style="CardBody.TLabel",
        )
        self.workspace_stats_label.grid(row=0, column=1, sticky="e")

    def build_sidebar(self):
        self.build_source_card().pack(fill="x")
        self.build_options_card().pack(fill="x", pady=(14, 0))
        self.build_action_card().pack(fill="x", pady=(14, 0))
        self.build_status_card().pack(fill="x", pady=(14, 0))
        self.build_metrics_card().pack(fill="x", pady=(14, 0))

    def build_source_card(self):
        card = ttk.Frame(self.sidebar, style="Card.TFrame", padding=16)
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="Source & Scraping", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            card,
            text="Use a preset typing site or provide a custom URL. The app will try the page HTML first, then fall back to a headless browser if Selenium is available.",
            style="CardBody.TLabel",
            wraplength=320,
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        ttk.Label(card, text="Preset site", style="CardBody.TLabel").grid(row=2, column=0, sticky="w")
        self.preset_combo = ttk.Combobox(card, textvariable=self.preset_var, values=list(self.presets.keys()), state="readonly")
        self.preset_combo.grid(row=3, column=0, sticky="ew", pady=(4, 10))

        ttk.Label(card, text="Website URL", style="CardBody.TLabel").grid(row=4, column=0, sticky="w")
        self.url_entry = ttk.Entry(card, textvariable=self.url_var)
        self.url_entry.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        return card

    def build_options_card(self):
        card = ttk.Frame(self.sidebar, style="Card.TFrame", padding=16)
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="Typing Controls", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            card,
            text="Tune the pacing before the countdown begins.",
            style="CardBody.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        ttk.Label(card, text="Duration (minutes)", style="CardBody.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(card, text="Countdown (seconds)", style="CardBody.TLabel").grid(row=2, column=1, sticky="w")

        self.duration_spin = ttk.Spinbox(card, from_=0.1, to=30.0, increment=0.1, textvariable=self.duration_var, width=10)
        self.duration_spin.grid(row=3, column=0, sticky="ew", pady=(4, 10), padx=(0, 6))

        self.countdown_spin = ttk.Spinbox(card, from_=1, to=10, increment=1, textvariable=self.countdown_var, width=10)
        self.countdown_spin.grid(row=3, column=1, sticky="ew", pady=(4, 10), padx=(6, 0))

        ttk.Checkbutton(
            card,
            text="Press Enter after typing",
            variable=self.enter_var,
            style="Muted.TCheckbutton",
        ).grid(row=4, column=0, columnspan=2, sticky="w")

        ttk.Checkbutton(
            card,
            text="Keep window always on top",
            variable=self.topmost_var,
            command=self.toggle_topmost,
            style="Muted.TCheckbutton",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return card

    def build_action_card(self):
        card = ttk.Frame(self.sidebar, style="Card.TFrame", padding=16)
        for column in range(2):
            card.columnconfigure(column, weight=1)

        ttk.Label(card, text="Run Actions", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            card,
            text="Choose whether to scrape only, scrape and type, or start a live watch for changing words.",
            style="CardBody.TLabel",
            wraplength=320,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        self.scrape_button = ttk.Button(card, text="Scrape Text", command=self.scrape_text_only, style="Secondary.TButton")
        self.scrape_button.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))

        self.scrape_type_button = ttk.Button(card, text="Scrape & Type", command=self.scrape_and_type, style="Accent.TButton")
        self.scrape_type_button.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(0, 8))

        self.type_button = ttk.Button(card, text="Start Typing", command=self.on_type, style="Accent.TButton")
        self.type_button.grid(row=3, column=0, sticky="ew", padx=(0, 6))

        self.just_type_button = ttk.Button(card, text="Just Type", command=self.on_type, style="Secondary.TButton")
        self.just_type_button.grid(row=3, column=1, sticky="ew", padx=(6, 0))

        self.live_scan_button = ttk.Button(card, text="Start Live Scan", command=self.start_realtime_scanning, style="Secondary.TButton")
        self.live_scan_button.grid(row=4, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))

        self.stop_button = ttk.Button(card, text="Stop", command=self.stop_all, style="Danger.TButton")
        self.stop_button.grid(row=4, column=1, sticky="ew", padx=(6, 0), pady=(8, 0))
        return card

    def build_status_card(self):
        card = ttk.Frame(self.sidebar, style="Card.TFrame", padding=16)
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="Session Status", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=self.status_var, style="Status.TLabel", wraplength=320).grid(row=1, column=0, sticky="w", pady=(8, 10))

        self.progress = ttk.Progressbar(card, variable=self.progress_var, maximum=100, style="Modern.Horizontal.TProgressbar")
        self.progress.grid(row=2, column=0, sticky="ew")
        return card

    def build_metrics_card(self):
        card = ttk.Frame(self.sidebar, style="SoftCard.TFrame", padding=16)
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="Session Metrics", style="SoftTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            card,
            text="Live stats update as you change text or pacing.",
            style="SoftBody.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        self.metric_box(card, "Words", self.words_var).grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
        self.metric_box(card, "Characters", self.characters_var).grid(row=2, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))
        self.metric_box(card, "Target pace", self.wpm_var).grid(row=3, column=0, sticky="nsew", padx=(0, 6))
        self.metric_box(card, "Delay per key", self.interval_var).grid(row=3, column=1, sticky="nsew", padx=(6, 0))
        return card

    def build_activity_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(fill="x", pady=(14, 0))
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="Activity Feed", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            card,
            text="Short status notes show what the app is doing in the background.",
            style="CardBody.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))

        self.activity_text = scrolledtext.ScrolledText(
            card,
            height=6,
            wrap="word",
            font=("Consolas", 10),
            bg=self.palette["card"],
            fg=self.palette["text"],
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
            state="disabled",
        )
        self.activity_text.grid(row=2, column=0, sticky="ew")
        self.log_event("App ready. Choose a source, then scrape or type when you are ready.")

    def metric_box(self, parent, label, value_var):
        frame = ttk.Frame(parent, style="SoftCard.TFrame", padding=12)
        ttk.Label(frame, text=label, style="MetricLabel.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=value_var, style="MetricValue.TLabel").pack(anchor="w", pady=(4, 0))
        return frame

    def bind_events(self):
        self.preset_combo.bind("<<ComboboxSelected>>", self.update_url_from_preset)
        self.text_widget.bind("<<Modified>>", self.on_text_modified)
        self.duration_var.trace_add("write", lambda *_: self.update_metrics())
        
        # Keyboard shortcuts
        self.root.bind("<Control-v>", lambda event: self.paste_from_clipboard())
        self.root.bind("<Control-V>", lambda event: self.paste_from_clipboard())
        self.root.bind("<Control-c>", lambda event: self.copy_text())
        self.root.bind("<Control-C>", lambda event: self.copy_text())
        self.root.bind("<Control-o>", lambda event: self.load_text_file())
        self.root.bind("<Control-O>", lambda event: self.load_text_file())
        self.root.bind("<Control-s>", lambda event: self.save_text_file())
        self.root.bind("<Control-S>", lambda event: self.save_text_file())
        self.root.bind("<Control-l>", lambda event: self.clear_text())
        self.root.bind("<Control-L>", lambda event: self.clear_text())
        self.root.bind("<Control-t>", lambda event: self.on_type())
        self.root.bind("<Control-T>", lambda event: self.on_type())
        self.root.bind("<Control-r>", lambda event: self.scrape_text_only())
        self.root.bind("<Control-R>", lambda event: self.scrape_text_only())
        self.root.bind("<Control-Shift-R>", lambda event: self.scrape_and_type())
        self.root.bind("<Control-Shift-T>", lambda event: self.start_realtime_scanning())
        self.root.bind("<Escape>", lambda event: self.stop_all())
        self.root.bind("<F5>", lambda event: self.toggle_theme())
        
        # Focus shortcuts
        self.root.bind("<Control-1>", lambda event: self.text_widget.focus_set())
        self.root.bind("<Control-2>", lambda event: self.url_entry.focus_set())
        self.root.bind("<Control-3>", lambda event: self.duration_spin.focus_set())

    def on_text_modified(self, _event=None):
        if self.text_widget.edit_modified():
            self.update_metrics()
            self.text_widget.edit_modified(False)

    def run_on_ui(self, callback, *args, **kwargs):
        try:
            self.root.after(0, lambda: callback(*args, **kwargs))
        except tk.TclError:
            return

    def log_event(self, message):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}\n"
        self.activity_text.configure(state="normal")
        self.activity_text.insert("end", entry)
        self.activity_text.see("end")
        self.activity_text.configure(state="disabled")

    def set_status(self, text, badge=None, progress=None, log_message=None):
        self.status_var.set(text)
        if badge is not None:
            self.badge_var.set(badge)
        if progress is not None:
            self.progress_var.set(progress)
        if log_message:
            self.log_event(log_message)

    def refresh_action_buttons(self):
        has_text = bool(self.get_text().strip())
        typing_busy = self.is_typing
        scraping_busy = self.is_scraping
        live_busy = self.realtime_scanning

        self.type_button.config(state="disabled" if typing_busy or scraping_busy or not has_text else "normal")
        self.scrape_button.config(state="disabled" if typing_busy or scraping_busy or live_busy else "normal")
        self.scrape_type_button.config(state="disabled" if typing_busy or scraping_busy or live_busy else "normal")
        self.live_scan_button.config(state="disabled" if typing_busy or scraping_busy or live_busy else "normal")
        self.stop_button.config(state="normal" if typing_busy or scraping_busy or live_busy else "disabled")

    def update_url_from_preset(self, _event=None):
        selected = self.preset_var.get()
        self.url_var.set(self.presets.get(selected, ""))

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())
        state = "enabled" if self.topmost_var.get() else "disabled"
        self.set_status(
            f"Always-on-top is now {state}.",
            badge=self.badge_var.get(),
            progress=self.progress_var.get(),
            log_message=f"Always-on-top {state}.",
        )

    def normalize_url(self):
        url = self.url_var.get().strip()
        if not url:
            return ""
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            url = f"https://{url}"
            self.url_var.set(url)
        return url

    def get_text(self):
        return self.text_widget.get("1.0", "end").strip()

    def set_text(self, text, source=None):
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        if source:
            self.source_var.set(source)
        self.update_metrics()

    def append_text(self, text):
        current = self.get_text()
        separator = " " if current and not current.endswith((" ", "\n")) else ""
        self.text_widget.insert("end", f"{separator}{text}")
        self.update_metrics()

    def clear_text(self):
        self.text_widget.delete("1.0", "end")
        self.source_var.set("Manual input")
        self.update_metrics()
        self.set_status("Text workspace cleared.", badge="Idle", progress=0, log_message="Workspace cleared.")
        self.show_success_toast("Text workspace cleared")

    def paste_from_clipboard(self):
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            self.show_warning_toast("Clipboard is empty")
            return

        if not clipboard_text.strip():
            self.show_warning_toast("Clipboard is empty")
            return

        self.set_text(clipboard_text, source="Clipboard")
        self.set_status(
            "Pasted text from the clipboard.",
            badge="Editing",
            progress=0,
            log_message="Loaded text from the clipboard.",
        )
        self.show_success_toast("Text pasted from clipboard")

    def copy_text(self):
        text = self.get_text()
        if not text:
            self.show_warning_toast("No text to copy")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status(
            "Text copied to the clipboard.",
            badge="Ready",
            progress=0,
            log_message="Copied the current text to the clipboard.",
        )
        self.show_success_toast("Text copied to clipboard")

    def load_text_file(self):
        path = filedialog.askopenfilename(
            title="Open text file",
            filetypes=[("Text files", "*.txt *.md *.log"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            text = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            self.show_error_toast(f"Could not read the file: {exc}")
            return

        self.set_text(text, source=f"File: {Path(path).name}")
        self.set_status(
            f"Loaded text from {Path(path).name}.",
            badge="Ready",
            progress=0,
            log_message=f"Loaded file {Path(path).name}.",
        )
        self.show_success_toast(f"Loaded {Path(path).name}")

    def save_text_file(self):
        text = self.get_text()
        if not text:
            self.show_warning_toast("No text to save")
            return

        path = filedialog.asksaveasfilename(
            title="Save text",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            self.show_error_toast(f"Could not save file: {exc}")
            return

        self.set_status(
            f"Saved text to {Path(path).name}.",
            badge="Ready",
            progress=0,
            log_message=f"Saved text to {Path(path).name}.",
        )
        self.show_success_toast(f"Saved {Path(path).name}")

    def update_metrics(self):
        text = self.get_text()
        words = len(text.split())
        characters = len(text)

        duration = self.safe_float(self.duration_var.get(), default=1.0)
        duration = max(duration, 0.1)
        target_wpm = (words / duration) if words else 0
        interval_ms = ((duration * 60) / characters * 1000) if characters else 0

        self.words_var.set(str(words))
        self.characters_var.set(str(characters))
        self.wpm_var.set(f"{target_wpm:.1f} wpm")
        self.interval_var.set(f"{interval_ms:.0f} ms")
        self.workspace_stats_label.config(text=f"{words} words - {characters} characters")
        self.refresh_action_buttons()

    @staticmethod
    def safe_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def scrape_text_only(self):
        self.start_scrape(auto_type=False)

    def scrape_and_type(self):
        self.start_scrape(auto_type=True)

    def start_scrape(self, auto_type=False):
        if requests is None or BeautifulSoup is None:
            messagebox.showerror(
                "Missing dependencies",
                "Scraping needs requests and beautifulsoup4.\nInstall with: python -m pip install requests beautifulsoup4",
            )
            return

        if self.is_scraping:
            messagebox.showwarning("Scraping already running", "A scrape is already in progress.")
            return

        url = self.normalize_url()
        if not url:
            messagebox.showwarning("No URL", "Enter a website URL or choose a preset typing site first.")
            return

        self.stop_event.clear()
        self.is_scraping = True
        self.refresh_action_buttons()
        message = "Scraping the page and preparing typing..." if auto_type else "Scraping the page for text..."
        self.set_status(message, badge="Scraping", progress=8, log_message=f"Started scrape for {url}.")

        worker = threading.Thread(target=self._scrape_worker, args=(url, auto_type), daemon=True)
        worker.start()

    def _scrape_worker(self, url, auto_type):
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            if self.stop_event.is_set():
                return
            soup = BeautifulSoup(response.content, "html.parser")

            self.run_on_ui(self.set_status, "HTML loaded. Extracting typing text...", "Scraping", 35, None)
            text_content = self.extract_typing_content(soup, url)

            if not text_content and webdriver is not None:
                self.run_on_ui(
                    self.set_status,
                    "The page looks dynamic. Trying a headless browser fallback...",
                    "Rendering",
                    55,
                    "Switching to Selenium fallback for dynamic content.",
                )
                rendered_html = self.render_page_with_selenium(url)
                if rendered_html:
                    rendered_soup = BeautifulSoup(rendered_html, "html.parser")
                    text_content = self.extract_typing_content(rendered_soup, url)

            if self.stop_event.is_set():
                return

            text_content = text_content.strip()
            if not text_content:
                raise ValueError(
                    "Could not extract typing text from the page. The site may hide words until you interact with it."
                )

            source_label = f"Scraped: {self.format_source_name(url)}"
            self.run_on_ui(self.apply_scraped_text, text_content, source_label, url, auto_type)
        except requests.exceptions.RequestException as exc:
            self.run_on_ui(
                self.handle_scrape_error,
                f"Failed to load the page:\n{exc}",
                "The page request failed.",
            )
        except Exception as exc:
            self.run_on_ui(
                self.handle_scrape_error,
                str(exc),
                "Scraping did not produce usable text.",
            )
        finally:
            self.run_on_ui(self.finish_scrape)

    def apply_scraped_text(self, text_content, source_label, url, auto_type):
        self.set_text(text_content, source=source_label)
        self.last_content = text_content
        self.set_status(
            "Typing text extracted successfully.",
            badge="Ready",
            progress=100,
            log_message=f"Scraped {len(text_content.split())} words from {self.format_source_name(url)}.",
        )

        if auto_type:
            self.root.after(250, lambda: self.start_typing_text(text_content, press_enter=self.enter_var.get()))

    def handle_scrape_error(self, message, log_message):
        messagebox.showerror("Scraping error", message)
        self.set_status("Scraping failed. Review the activity feed or try a different site.", badge="Idle", progress=0, log_message=log_message)

    def finish_scrape(self):
        self.is_scraping = False
        if self.stop_event.is_set() and not self.is_typing and not self.realtime_scanning:
            self.set_status("Scraping stopped.", badge="Idle", progress=0, log_message="Scrape stopped by the user.")
        elif not self.is_typing and not self.realtime_scanning and self.progress_var.get() >= 100:
            self.progress_var.set(0)
        self.refresh_action_buttons()

    def start_realtime_scanning(self):
        if requests is None or BeautifulSoup is None:
            messagebox.showerror(
                "Missing dependencies",
                "Live scanning needs requests and beautifulsoup4.\nInstall with: python -m pip install requests beautifulsoup4",
            )
            return

        if self.realtime_scanning:
            messagebox.showinfo("Live scan active", "Live scanning is already running.")
            return

        url = self.normalize_url()
        if not url:
            messagebox.showwarning("No URL", "Enter a website URL before starting live scan.")
            return

        self.stop_event.clear()
        self.realtime_scanning = True
        self.last_content = ""
        self.set_status(
            "Watching the page for changing typing words...",
            badge="Watching",
            progress=15,
            log_message=f"Started live scan for {url}.",
        )
        self.refresh_action_buttons()

        self.scanning_thread = threading.Thread(target=self.realtime_scan_loop, args=(url,), daemon=True)
        self.scanning_thread.start()

    def realtime_scan_loop(self, url):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }

        while self.realtime_scanning and not self.stop_event.is_set():
            try:
                response = requests.get(url, headers=headers, timeout=6)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                current_content = self.extract_typing_content(soup, url)

                if not current_content and webdriver is not None:
                    rendered_html = self.render_page_with_selenium(url)
                    if rendered_html:
                        current_content = self.extract_typing_content(BeautifulSoup(rendered_html, "html.parser"), url)

                if current_content:
                    current_content = current_content.strip()
                    if not self.last_content:
                        self.last_content = current_content
                        self.run_on_ui(
                            self.set_status,
                            "Live scan connected. Waiting for new words...",
                            "Watching",
                            20,
                            "Live scan baseline captured.",
                        )
                    elif current_content != self.last_content:
                        new_words = self.get_new_words(current_content, self.last_content)
                        self.last_content = current_content
                        if new_words.strip():
                            self.run_on_ui(self.handle_new_content, new_words, url)

                for _ in range(20):
                    if not self.realtime_scanning or self.stop_event.is_set():
                        break
                    time.sleep(0.1)
            except Exception:
                for _ in range(30):
                    if not self.realtime_scanning or self.stop_event.is_set():
                        break
                    time.sleep(0.1)

        self.run_on_ui(self.finish_live_scan)

    def finish_live_scan(self):
        self.realtime_scanning = False
        if not self.is_typing and not self.is_scraping:
            self.set_status("Live scanning stopped.", badge="Idle", progress=0, log_message="Live scan stopped.")
        self.refresh_action_buttons()

    def handle_new_content(self, new_words, url):
        self.append_text(new_words)
        self.source_var.set(f"Live scan: {self.format_source_name(url)}")
        self.set_status(
            "New words detected and added to the workspace.",
            badge="Watching",
            progress=35,
            log_message=f"Detected {len(new_words.split())} new words.",
        )

        if not self.is_typing:
            self.root.after(250, lambda: self.start_typing_text(new_words, press_enter=False))

    def get_new_words(self, current_content, last_content):
        if not last_content:
            return current_content

        current_words = current_content.split()
        last_words = last_content.split()
        min_length = min(len(current_words), len(last_words))
        divergence_point = min_length

        for index in range(min_length):
            if current_words[index] != last_words[index]:
                divergence_point = index
                break

        return " ".join(current_words[divergence_point:])

    def on_type(self):
        self.start_typing_text(self.get_text(), press_enter=self.enter_var.get())

    def start_typing_text(self, text, press_enter):
        if pyautogui is None:
            messagebox.showerror(
                "Missing dependency",
                "Typing automation needs pyautogui.\nInstall with: python -m pip install pyautogui",
            )
            return

        if self.is_typing:
            messagebox.showwarning("Already typing", "Typing is already in progress.")
            return

        text = text.strip()
        if not text:
            messagebox.showwarning("No text", "Add or scrape some text before starting typing.")
            return

        duration = max(self.safe_float(self.duration_var.get(), default=1.0), 0.1)
        countdown = max(int(self.safe_float(self.countdown_var.get(), default=3)), 1)

        self.stop_event.clear()
        self.is_typing = True
        self.refresh_action_buttons()
        self.set_status(
            "Countdown ready. Click your target field before typing begins.",
            badge="Typing",
            progress=0,
            log_message=f"Typing scheduled for {len(text.split())} words over {duration:.1f} minute(s).",
        )

        self.typing_thread = threading.Thread(
            target=self.type_text,
            args=(text, duration, press_enter, countdown),
            daemon=True,
        )
        self.typing_thread.start()

    def type_text(self, text, duration, press_enter, countdown):
        try:
            for remaining in range(countdown, 0, -1):
                if self.stop_event.is_set():
                    self.run_on_ui(self.finish_typing, False, True, None)
                    return

                progress = ((countdown - remaining) / max(countdown, 1)) * 15
                self.run_on_ui(
                    self.set_status,
                    f"Typing starts in {remaining} second(s). Click the destination field now.",
                    "Typing",
                    progress,
                    None,
                )

                for _ in range(10):
                    if self.stop_event.is_set():
                        self.run_on_ui(self.finish_typing, False, True, None)
                        return
                    time.sleep(0.1)

            pyautogui.FAILSAFE = False
            char_count = len(text)
            if char_count == 0:
                self.run_on_ui(self.finish_typing, False, True, None)
                return

            interval = (duration * 60) / char_count
            progress_step = max(char_count // 100, 1)
            self.run_on_ui(
                self.set_status,
                "Typing in progress...",
                "Typing",
                18,
                "Countdown finished. Typing started.",
            )

            for index, char in enumerate(text, start=1):
                if self.stop_event.is_set():
                    self.run_on_ui(self.finish_typing, False, True, None)
                    return

                pyautogui.write(char, interval=interval)

                if index == char_count or index % progress_step == 0:
                    progress = 18 + ((index / char_count) * 82)
                    self.run_on_ui(
                        self.set_status,
                        f"Typing in progress... {index}/{char_count} characters sent.",
                        "Typing",
                        progress,
                        None,
                    )

            if press_enter and not self.stop_event.is_set():
                pyautogui.press("enter")

            self.run_on_ui(self.finish_typing, True, False, None)
        except Exception as exc:
            self.run_on_ui(self.finish_typing, False, False, str(exc))

    def finish_typing(self, success, stopped, error_message):
        self.is_typing = False
        self.progress_var.set(0)

        if error_message:
            messagebox.showerror("Typing error", f"Unable to type text:\n{error_message}")
            self.set_status("Typing failed. Check the target app and try again.", badge="Idle", progress=0, log_message="Typing failed with an automation error.")
        elif stopped:
            if self.realtime_scanning:
                self.set_status("Typing stopped. Live scan can still be restarted if needed.", badge="Idle", progress=0, log_message="Typing stopped by the user.")
            else:
                self.set_status("Typing stopped.", badge="Idle", progress=0, log_message="Typing stopped by the user.")
        elif success:
            self.set_status("Typing complete.", badge="Done", progress=100, log_message="Typing finished successfully.")
            self.root.after(1000, lambda: self.set_status("Ready for the next run.", badge="Idle", progress=0, log_message=None))

        self.refresh_action_buttons()

    def stop_all(self):
        was_busy = self.is_typing or self.is_scraping or self.realtime_scanning
        self.stop_event.set()
        self.realtime_scanning = False
        self.is_scraping = False

        if was_busy:
            self.set_status("Stopping active work...", badge="Stopping", progress=5, log_message="Stop requested for active tasks.")
        else:
            self.set_status("Nothing is running right now.", badge="Idle", progress=0, log_message="Stop clicked while idle.")

        self.refresh_action_buttons()

    def extract_typing_content(self, soup, url):
        url_lower = url.lower()

        if "livechat.com" in url_lower:
            livechat_text = self.extract_livechat_words(soup.get_text(" ", strip=True))
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
            candidate = self.join_visible_text(elements)
            if self.looks_like_typing_text(candidate):
                return candidate

        script_candidate = self.extract_words_from_scripts(soup)
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
            candidate = self.clean_text(self.join_visible_text(elements))
            if self.looks_like_typing_text(candidate):
                return candidate

        page_text = self.clean_text(soup.get_text(" ", strip=True))
        if self.looks_like_typing_text(page_text):
            return " ".join(page_text.split()[:120])

        return ""

    def extract_livechat_words(self, page_text):
        compact = re.sub(r"[^a-z]", "", page_text.lower())
        pattern = r"([a-z]{45,})"
        match = re.search(pattern, compact)
        if not match:
            return ""

        chunk = match.group(1)
        words = []
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

    def join_visible_text(self, elements):
        chunks = []
        for element in elements:
            text = element.get_text(" ", strip=True)
            if text:
                chunks.append(text)
        return self.clean_text(" ".join(chunks))

    def clean_text(self, text):
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        return text

    def looks_like_typing_text(self, text):
        if not text or len(text) < 30:
            return False

        words = re.findall(r"[A-Za-z][A-Za-z'-]{1,}", text)
        unique_words = len(set(word.lower() for word in words))
        return len(words) >= 8 and unique_words >= 4

    def extract_words_from_scripts(self, soup):
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

    def render_page_with_selenium(self, url, timeout=15):
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

    def format_source_name(self, url):
        parsed = urlparse(url)
        host = parsed.netloc.replace("www.", "")
        return host or url


def main():
    root = tk.Tk()
    app = OverlayTyperApp(root)

    def on_closing():
        app.stop_event.set()
        app.realtime_scanning = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
