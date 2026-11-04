# ScreenShutter

A lightweight Windows screenshot utility built with Python and Tkinter.

## Features

- Full-screen, active-window, and drag-to-select region capture across the full virtual desktop
- Main window opens centered on the monitor containing the mouse cursor
- Global shortcut (default: `Shift+Print Screen`)
- PNG, JPEG, WEBP, BMP, and TIFF output
- Adjustable JPEG/WEBP quality
- Configurable screenshot folder
- Optional Windows startup shortcut
- Preview before saving
- System-tray icon with **Open ScreenShutter** and **Exit** actions
- Closing the settings window keeps ScreenShutter running in the tray; **Fully Exit** quits it

## Requirements

- Windows 10 or later
- Python 3.10+
- Tkinter (included with standard Windows Python installers)
- Pillow
- pywin32
- pystray

Install dependencies:

```bat
py -m pip install -r requirements.txt
```

Run from source:

```bat
py app.py
```

## Build with Nuitka

Run:

```bat
build.bat
```

This creates a standalone build at `build\ScreenShutter.dist\ScreenShutter.exe`.

For a single-file executable instead:

```bat
build.bat onefile
```

The one-file executable is written to `build\ScreenShutter.exe`. The build script installs the project dependencies and Nuitka before compiling. Run the build on Windows; cross-compiling from Linux is not supported.

## Tray behavior

- Closing the main window hides it to the system tray.
- Use **Open ScreenShutter** in the tray menu or press the configured global shortcut to reopen it.
- Use **Fully Exit** in the main window or **Exit** in the tray menu to terminate the process.

The global shortcut uses the Win32 `RegisterHotKey` API. Windows may reject a shortcut already claimed by another application.
