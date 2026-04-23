# Overlay Typer Bot

A modern, feature-rich desktop automation application for typing text with realistic human-like pacing. Built with Python and Tkinter, featuring a clean interface with dark mode support, keyboard shortcuts, and smart web scraping capabilities.

## ✨ Features

### Core Functionality
- **Realistic Typing Simulation**: Types text character by character with customizable timing
- **Smart Web Scraping**: Automatically extracts typing text from popular typing test websites
- **Live Scanning Mode**: Monitors websites for changing content and auto-types new words
- **File Operations**: Load, save, copy, and paste text directly from the interface
- **Real-time Metrics**: Live statistics for words, characters, WPM, and typing intervals

### Modern UI Features
- **🌙 Dark Mode**: Toggle between light and dark themes with smooth transitions
- **⌨️ Keyboard Shortcuts**: Comprehensive hotkey support for all major functions
- **🔔 Toast Notifications**: Modern, non-intrusive feedback for user actions
- **💾 Settings Persistence**: Automatically saves your preferences and settings
- **📱 Responsive Design**: Clean, modern interface that adapts to window resizing

### Automation & Scraping
- **Preset Websites**: Built-in support for popular typing test sites
- **Selenium Fallback**: Automatic headless browser for dynamic content
- **Custom URLs**: Support for any typing website
- **Live Content Monitoring**: Real-time scanning for updated typing content

## 🚀 Quick Start

### Prerequisites
- **Windows** (primary support)
- **Python 3.10+**
- **Google Chrome** (optional, for Selenium fallback)

### Installation

1. **Clone or Download**
   ```powershell
   git clone <your-repo-url>
   cd "new bot"
   ```

2. **Create Virtual Environment**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```powershell
   python -m pip install -r requirements.txt
   ```

4. **Run the Application**
   ```powershell
   python main.py
   ```

5. **Run the Web Version**
   ```powershell
   .\start_web.ps1
   ```
   Then open `http://127.0.0.1:5000` in your browser.

## Web Access

The project now also includes a browser interface in `web_app.py`.

- Run `python web_app.py`, then open `http://127.0.0.1:5000`.
- If the `python` launcher is unavailable on your machine, run `.\start_web.ps1` from PowerShell and it will locate a working local Python install automatically.
- Use the website to paste text, scrape supported typing pages, view metrics, and run timed typing playback inside the browser.
- The original Tkinter desktop app in `main.py` is still available for desktop-wide automation with `pyautogui`.
- The scrape endpoint only accepts public `http` and `https` URLs and blocks local or private hosts.

## 📖 Usage Guide

### Basic Typing
1. **Add Text**: Paste text, load from file, or scrape from a website
2. **Configure Settings**: Set duration (minutes) and countdown (seconds)
3. **Start Typing**: Click "Start Typing" or press `Ctrl+T`
4. **Focus Target**: During countdown, click where you want typing to occur

### Web Scraping
1. **Select Source**: Choose a preset or enter a custom URL
2. **Scrape Options**:
   - `Scrape Text` (`Ctrl+R`): Extract text only
   - `Scrape & Type` (`Ctrl+Shift+R`): Extract and auto-type
3. **Live Mode** (`Ctrl+Shift+T`): Monitor for content changes

### File Operations
- **Load File** (`Ctrl+O`): Import text from local files
- **Save Text** (`Ctrl+S`): Export current workspace content
- **Copy** (`Ctrl+C`): Copy to clipboard
- **Paste** (`Ctrl+V`): Paste from clipboard
- **Clear** (`Ctrl+L`): Clear workspace

## ⌨️ Keyboard Shortcuts

| Function | Shortcut | Description |
|----------|----------|-------------|
| **Text Operations** | | |
| Paste | `Ctrl+V` | Paste from clipboard |
| Copy | `Ctrl+C` | Copy to clipboard |
| Load File | `Ctrl+O` | Open file dialog |
| Save Text | `Ctrl+S` | Save to file |
| Clear | `Ctrl+L` | Clear workspace |
| **Actions** | | |
| Start Typing | `Ctrl+T` | Begin typing simulation |
| Scrape Text | `Ctrl+R` | Scrape website only |
| Scrape & Type | `Ctrl+Shift+R` | Scrape and auto-type |
| Live Scan | `Ctrl+Shift+T` | Start live monitoring |
| Stop | `Escape` | Stop all operations |
| **Interface** | | |
| Toggle Theme | `F5` | Switch light/dark mode |
| Focus Text | `Ctrl+1` | Focus text editor |
| Focus URL | `Ctrl+2` | Focus URL field |
| Focus Duration | `Ctrl+3` | Focus duration setting |

## 🎨 Interface Features

### Theme System
- **Light Theme**: Clean, bright interface for daytime use
- **Dark Theme**: Easy-on-the-eyes dark mode for extended sessions
- **Auto-save**: Theme preference remembered between sessions

### Status Indicators
- **Live Badge**: Shows current app state (Idle, Typing, Scraping, etc.)
- **Progress Bar**: Visual feedback for ongoing operations
- **Activity Feed**: Timestamped log of all app activities

### Metrics Dashboard
- **Word Count**: Real-time word statistics
- **Character Count**: Character tracking including spaces
- **Target WPM**: Calculated words-per-minute based on duration
- **Key Delay**: Millisecond delay between keystrokes

## 🌐 Supported Websites

### Built-in Presets
- **LiveChat Typing Test**: `https://www.livechat.com/typing-speed-test/#/`
- **10FastFingers**: `https://10fastfingers.com/typing-test/english`
- **TypingTest.com**: `https://www.typingtest.com/`
- **Monkeytype**: `https://monkeytype.com/`

### Custom Sites
The app works with most typing test websites that:
- Use standard HTML elements for word display
- Include typing words in JavaScript arrays
- Have accessible text content in page structure

## ⚙️ Configuration

### Settings Persistence
The app automatically saves:
- Theme preference (light/dark mode)
- Last selected preset
- Typing duration and countdown
- Enter key preference
- Always-on-top setting

Settings are stored in `settings.json` in the app directory.

### Advanced Options
- **Selenium Integration**: Automatic fallback for JavaScript-heavy sites
- **Custom User-Agent**: Built-in browser identification
- **Error Handling**: Graceful degradation for unsupported sites

## 🔧 Troubleshooting

### Common Issues

**App won't start**
- Ensure Python 3.10+ is installed
- Verify all dependencies from `requirements.txt` are installed
- Check if Tkinter is available (included with most Python installations)

**Typing goes to wrong window**
- Use the countdown time to click the correct input field
- Ensure no other windows steal focus during typing
- Try shorter countdown for better timing

**Scraping fails**
- Test with preset sites first
- Check internet connection
- Install Chrome for Selenium fallback support
- Verify URL loads in regular browser

**Keyboard shortcuts not working**
- Ensure the app window has focus
- Check for conflicting system shortcuts
- Try clicking in the app first, then use shortcuts

### Dependencies Issues

**Missing Chrome for Selenium**
```powershell
# Download and install Chrome, then reinstall dependencies
python -m pip install --upgrade selenium webdriver-manager
```

**Import errors**
```powershell
# Reinstall all dependencies
python -m pip install -r requirements.txt --force-reinstall
```

## 📁 Project Structure

```
new bot/
├── main.py              # Main application file
├── requirements.txt     # Python dependencies
├── settings.json       # User preferences (auto-generated)
└── README.md          # This documentation
```

## 🛠️ Development

### Dependencies
- **pyautogui**: Screen automation and typing simulation
- **requests**: HTTP requests for web scraping
- **beautifulsoup4**: HTML parsing
- **selenium**: Browser automation for dynamic content
- **webdriver-manager**: Automatic Chrome driver management

### Extending the App
The modular design allows for easy extension:
- Add new preset sites in the `presets` dictionary
- Implement custom scrapers in `extract_typing_content()`
- Add new themes in `setup_theme()`
- Extend keyboard shortcuts in `bind_events()`

## 📄 License

This project is provided as-is for educational and personal use. Please respect the terms of service of websites you automate.

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests to improve the application.

---

**Version**: 2.0  
**Last Updated**: 2025  
**Compatibility**: Windows 10+, Python 3.10+
