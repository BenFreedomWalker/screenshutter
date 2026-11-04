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

Closing the window minimizes the app to the background. Use the tray-free initial prototype's global shortcut to reopen its settings window. Exit with the window's normal close action only after using the app's process exit mechanism in a future version; the initial prototype currently keeps running in the background.

## Notes

This is an early prototype. The global shortcut is registered with the Win32 `RegisterHotKey` API. Windows may reject a shortcut already claimed by another application. Multi-monitor region selection and mixed-DPI behavior need additional testing.
