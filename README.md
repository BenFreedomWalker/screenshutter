# ScreenShutter

A lightweight Windows screenshot utility built with Python and Tkinter.

## Features

- Full-screen, active-window, and drag-to-select region capture
- Global shortcut (default: `Shift+Print Screen`)
- PNG, JPEG, WEBP, BMP, and TIFF output
- Adjustable JPEG/WEBP quality
- Configurable screenshot folder
- Optional Windows startup shortcut
- Preview before saving

## Requirements

- Windows 10 or later
- Python 3.10+
- Tkinter (included with standard Windows Python installers)
- Pillow
- pywin32 (used to create/remove the Windows startup shortcut)

Install dependencies:

```bat
py -m pip install -r requirements.txt
```

Run:

```bat
py app.py
```

Closing the settings window hides ScreenShutter in the background. Press the configured global shortcut to reopen it. Use the **Exit** button in the main window to quit the application.

## Notes

This is an early prototype. The global shortcut is registered with the Win32 `RegisterHotKey` API. Windows may reject a shortcut already claimed by another application. Multi-monitor region selection and mixed-DPI behavior need additional testing.
