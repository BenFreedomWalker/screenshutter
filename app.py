import ctypes
import ctypes.wintypes
import os
import queue
import re
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pystray
from PIL import Image, ImageDraw, ImageGrab

from license_text import LICENSE_TEXT

APP_NAME = "ScreenShutter"
DEFAULT_HOTKEY = "Shift+Print Screen"
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
HOTKEY_ID = 1
PRINTSCREEN_HOTKEY_ID = 2
PRINTSCREEN_VK = 0x2C

MONITOR_DEFAULTTONEAREST = 2
SWP_SHOWWINDOW = 0x0040
HWND_TOP = ctypes.c_void_p(0)
HWND_TOPMOST = ctypes.c_void_p(-1)
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.wintypes.LONG), ("y", ctypes.wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.wintypes.LONG), ("top", ctypes.wintypes.LONG),
                ("right", ctypes.wintypes.LONG), ("bottom", ctypes.wintypes.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.wintypes.DWORD)]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = ctypes.wintypes.BOOL
user32.MonitorFromPoint.argtypes = [POINT, ctypes.wintypes.DWORD]
user32.MonitorFromPoint.restype = ctypes.wintypes.HANDLE
user32.GetMonitorInfoW.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = ctypes.wintypes.BOOL
user32.SetWindowPos.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HWND, ctypes.wintypes.INT,
                                ctypes.wintypes.INT, ctypes.wintypes.INT, ctypes.wintypes.INT,
                                ctypes.wintypes.UINT]
user32.SetWindowPos.restype = ctypes.wintypes.BOOL
user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT]
user32.GetAncestor.restype = ctypes.wintypes.HWND


def parse_hotkey(spec):
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    modifiers = 0
    key_name = None
    for part in parts:
        if part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part == "shift":
            modifiers |= MOD_SHIFT
        elif part == "alt":
            modifiers |= MOD_ALT
        elif part in ("win", "windows", "super"):
            modifiers |= MOD_WIN
        else:
            if key_name is not None:
                raise ValueError("Use one non-modifier key in the shortcut.")
            key_name = part

    if not key_name:
        raise ValueError("The shortcut needs a key, for example Shift+Print Screen.")

    aliases = {
        "print screen": 0x2C, "printscreen": 0x2C, "prtsc": 0x2C,
        "space": 0x20, "enter": 0x0D, "escape": 0x1B,
        "tab": 0x09, "delete": 0x2E, "insert": 0x2D,
        "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    }
    if key_name in aliases:
        vk = aliases[key_name]
    elif re.fullmatch(r"f(?:[1-9]|1[0-2])", key_name):
        vk = 0x70 + int(key_name[1:]) - 1
    elif len(key_name) == 1 and key_name.isalnum():
        vk = ord(key_name.upper())
    else:
        raise ValueError("Unsupported key. Try a letter, number, F1-F12, or Print Screen.")
    if vk == PRINTSCREEN_VK and modifiers == 0:
        raise ValueError("Print Screen is reserved for the selected screenshot mode. Choose a shortcut with at least one modifier.")
    return modifiers | MOD_NOREPEAT, vk


class HotkeyListener:
    def __init__(self, callback):
        self.callback = callback
        self.thread = None
        self.thread_id = None
        self.ready = threading.Event()
        self.error = None
        self.running = False

    def start(self, spec):
        # Validate before stopping the active registrations, so a rejected
        # shortcut never leaves Print Screen unbound.
        modifiers, vk = parse_hotkey(spec)
        self.stop()
        self.ready.clear()
        self.error = None
        self.running = True

        def worker():
            self.thread_id = kernel32.GetCurrentThreadId()
            registered = []
            try:
                if not user32.RegisterHotKey(None, HOTKEY_ID, modifiers, vk):
                    raise ctypes.WinError()
                registered.append(HOTKEY_ID)
                # Print Screen always performs the currently selected capture mode.
                if not user32.RegisterHotKey(None, PRINTSCREEN_HOTKEY_ID, MOD_NOREPEAT, PRINTSCREEN_VK):
                    error = ctypes.WinError()
                    raise RuntimeError(f"Could not reserve Print Screen for capture. Another application or Windows may be using it. {error}")
                registered.append(PRINTSCREEN_HOTKEY_ID)
                self.ready.set()
                msg = ctypes.wintypes.MSG()
                while self.running:
                    result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if result <= 0:
                        break
                    if msg.message == WM_HOTKEY:
                        if msg.wParam == HOTKEY_ID:
                            self.callback("window")
                        elif msg.wParam == PRINTSCREEN_HOTKEY_ID:
                            self.callback("printscreen")
            except Exception as exc:
                self.error = exc
                self.ready.set()
            finally:
                for hotkey_id in registered:
                    user32.UnregisterHotKey(None, hotkey_id)

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()
        self.ready.wait(timeout=2)
        if self.error:
            raise self.error

    def stop(self):
        self.running = False
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread_id = None


class ScreenShutter:
    def __init__(self, root, start_hidden=False):
        self.root = root
        self.root.title("ScreenShutter")
        self.icon_path = Path(__file__).resolve().parent / "assets" / "screenshutter.ico"
        if self.icon_path.is_file():
            try:
                self.root.iconbitmap(default=str(self.icon_path))
            except tk.TclError:
                pass
        self.window_geometry = "560x600"
        self.root.geometry(self.window_geometry)
        self.root.minsize(520, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.settings_dir = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self.settings_file = self.settings_dir / "settings.ini"

        self.save_dir = tk.StringVar(value=str(Path.home() / "Pictures" / "ScreenShutter"))
        self.image_format = tk.StringVar(value="PNG")
        self.quality = tk.IntVar(value=90)
        self.hotkey = tk.StringVar(value=DEFAULT_HOTKEY)
        self.printscreen_mode = tk.StringVar(value="Full screen")
        self.preview_enabled = tk.BooleanVar(value=True)
        self.startup = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Ready")
        self.hotkey_listener = HotkeyListener(self.hotkey_pressed)
        self.hotkey_queue = queue.Queue()
        self.tray_icon = None
        self.tray_thread = None
        self.about_window = None

        self.load_settings()
        self.build_ui()
        if not start_hidden:
            self.position_window_at_cursor()
        self.start_tray_icon()
        self.apply_format_state()
        self.root.after(100, self.process_queue)
        self.root.after(300, self.register_hotkey)

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="ScreenShutter", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(outer, text="A simple Windows screenshot tool", foreground="#666").pack(anchor="w", pady=(0, 16))

        capture = ttk.LabelFrame(outer, text="Take a screenshot", padding=12)
        capture.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(capture)
        row.pack(fill="x")
        ttk.Button(row, text="Full screen", command=self.capture_full).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ttk.Button(row, text="Active window", command=self.capture_window).pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(row, text="Select region", command=self.select_region).pack(side="left", expand=True, fill="x", padx=(5, 0))

        settings = ttk.LabelFrame(outer, text="Settings", padding=12)
        settings.pack(fill="both", expand=True)

        ttk.Label(settings, text="Save screenshots to").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(settings, textvariable=self.save_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(settings, text="Browse…", command=self.browse_folder).grid(row=0, column=2)

        ttk.Label(settings, text="Image format").grid(row=1, column=0, sticky="w", pady=5)
        formats = ("PNG", "JPEG", "WEBP", "BMP", "TIFF")
        format_box = ttk.Combobox(settings, textvariable=self.image_format, values=formats, state="readonly", width=12)
        format_box.grid(row=1, column=1, sticky="w", padx=8)
        format_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_format_state())

        ttk.Label(settings, text="Quality").grid(row=2, column=0, sticky="w", pady=5)
        quality_row = ttk.Frame(settings)
        quality_row.grid(row=2, column=1, columnspan=2, sticky="ew", padx=8)
        self.quality_scale = ttk.Scale(quality_row, from_=1, to=100, variable=self.quality, command=self.update_quality_label)
        self.quality_scale.pack(side="left", fill="x", expand=True)
        self.quality_label = ttk.Label(quality_row, text="90", width=4)
        self.quality_label.pack(side="left", padx=(8, 0))

        ttk.Label(settings, text="Print Screen action").grid(row=3, column=0, sticky="w", pady=5)
        mode_box = ttk.Combobox(settings, textvariable=self.printscreen_mode,
                                values=("Full screen", "Active window", "Select region"),
                                state="readonly", width=18)
        mode_box.grid(row=3, column=1, sticky="w", padx=8)

        ttk.Label(settings, text="Window shortcut").grid(row=4, column=0, sticky="w", pady=5)
        shortcut_row = ttk.Frame(settings)
        shortcut_row.grid(row=4, column=1, columnspan=2, sticky="ew", padx=8)
        ttk.Entry(shortcut_row, textvariable=self.hotkey).pack(side="left", fill="x", expand=True)
        ttk.Button(shortcut_row, text="Apply", command=self.register_hotkey).pack(side="left", padx=(6, 0))

        ttk.Checkbutton(settings, text="Show preview before saving", variable=self.preview_enabled,
                        command=self.save_settings).grid(row=5, column=1, columnspan=2, sticky="w", pady=5)

        ttk.Checkbutton(settings, text="Start ScreenShutter with Windows", variable=self.startup,
                        command=self.toggle_startup).grid(row=6, column=1, columnspan=2, sticky="w", pady=5)
        settings.columnconfigure(1, weight=1)

        ttk.Label(outer, textvariable=self.status, anchor="w").pack(fill="x", pady=(12, 0))
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(5, 0))
        ttk.Label(footer, text="Close this window to keep ScreenShutter running. Use Fully Exit to quit completely.",
                  foreground="#666", wraplength=360).pack(side="left", anchor="w")
        ttk.Button(footer, text="About", command=self.show_about).pack(side="right", padx=(0, 6))
        ttk.Button(footer, text="Fully Exit", command=self.close).pack(side="right")

    def show_about(self):
        if self.about_window and self.about_window.winfo_exists():
            self.about_window.deiconify()
            self.about_window.lift()
            self.about_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self.about_window = window
        window.title("About ScreenShutter")
        window.geometry("760x720")
        window.minsize(560, 500)
        window.transient(self.root)

        heading = ttk.Frame(window, padding=(16, 14, 16, 8))
        heading.pack(fill="x")
        ttk.Label(heading, text="ScreenShutter", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(heading, text="A simple Windows screenshot tool").pack(anchor="w", pady=(2, 0))
        ttk.Label(heading, text="Licensed under the GNU General Public License, version 3.").pack(
            anchor="w", pady=(6, 0)
        )

        support_frame = ttk.LabelFrame(window, text="Support development", padding=10)
        support_frame.pack(fill="x", padx=16, pady=(4, 10))
        ttk.Label(
            support_frame,
            text="Enjoying ScreenShutter? Support me on Keeper.",
        ).pack(anchor="w", pady=(0, 7))

        wallet_row = ttk.Frame(support_frame)
        wallet_row.pack(fill="x")
        ttk.Label(wallet_row, text="GRAM address:").pack(side="left")
        gram_address = "UQBYSIOzAMkxo1ZWbsFbg7-1vZd2cZbXsEQqYJzlNq5b1_Y1"
        wallet_entry = ttk.Entry(wallet_row)
        wallet_entry.insert(0, gram_address)
        wallet_entry.configure(state="readonly")
        wallet_entry.pack(side="left", fill="x", expand=True, padx=8)

        def copy_gram_address():
            window.clipboard_clear()
            window.clipboard_append(gram_address)
            window.update()
            copy_button.configure(text="Copied")
            window.after(1500, lambda: copy_button.configure(text="Copy"))

        copy_button = ttk.Button(wallet_row, text="Copy", command=copy_gram_address)
        copy_button.pack(side="right")

        license_frame = ttk.LabelFrame(window, text="GNU General Public License v3", padding=8)
        license_frame.pack(fill="both", expand=True, padx=16, pady=(4, 10))
        license_scroll = ttk.Scrollbar(license_frame)
        license_scroll.pack(side="right", fill="y")
        license_view = tk.Text(
            license_frame,
            wrap="word",
            font=("Consolas", 9),
            padx=8,
            pady=8,
            yscrollcommand=license_scroll.set,
            undo=False,
        )
        license_view.pack(side="left", fill="both", expand=True)
        license_scroll.configure(command=license_view.yview)
        license_view.insert("1.0", LICENSE_TEXT)
        license_view.configure(state="disabled")

        issue_frame = ttk.Frame(window, padding=(16, 0, 16, 12))
        issue_frame.pack(fill="x")
        ttk.Label(issue_frame, text="Found a problem? Please report it here:").pack(anchor="w")
        issue_link = ttk.Label(
            issue_frame,
            text="https://github.com/BenFreedomWalker/screenshutter/issues",
            foreground="#0969da",
            cursor="hand2",
        )
        issue_link.pack(anchor="w", pady=(3, 8))
        issue_link.bind(
            "<Button-1>",
            lambda _event: webbrowser.open_new_tab(
                "https://github.com/BenFreedomWalker/screenshutter/issues"
            ),
        )
        ttk.Button(issue_frame, text="Close", command=window.destroy).pack(side="right")

        def clear_about_reference(_event=None):
            self.about_window = None

        window.bind("<Destroy>", lambda event: clear_about_reference() if event.widget is window else None)
        window.protocol("WM_DELETE_WINDOW", window.destroy)

    def update_quality_label(self, _value=None):
        self.quality_label.configure(text=str(int(float(self.quality.get()))))

    def apply_format_state(self):
        enabled = self.image_format.get() in ("JPEG", "WEBP")
        self.quality_scale.configure(state="normal" if enabled else "disabled")

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.save_dir.get() or str(Path.home()))
        if folder:
            self.save_dir.set(folder)

    def register_hotkey(self):
        try:
            self.hotkey_listener.start(self.hotkey.get())
            self.status.set(f"Print Screen: {self.printscreen_mode.get()} | Window shortcut: {self.hotkey.get()}")
        except Exception as exc:
            self.status.set(f"Could not register shortcut: {exc}")
            messagebox.showerror(
                "Shortcut error",
                f"Could not register {self.hotkey.get()}.\n\n{exc}"
            )

    def hotkey_pressed(self, action):
        self.hotkey_queue.put(action)

    def process_queue(self):
        try:
            while True:
                action = self.hotkey_queue.get_nowait()
                if action in ("window", "show"):
                    self.show_window()
                elif action == "printscreen":
                    self.capture_selected_mode()
                elif action == "exit":
                    self.close()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def start_tray_icon(self):
        if self.icon_path.is_file():
            image = Image.open(self.icon_path).convert("RGBA")
        else:
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((4, 4, 60, 60), radius=12, fill="#202938")
            draw.rounded_rectangle((13, 15, 51, 43), radius=4, fill="#edf4fb")
            draw.ellipse((23, 20, 41, 38), fill="#168bd2")
            draw.rounded_rectangle((25, 46, 39, 50), radius=2, fill="#edf4fb")
            draw.rounded_rectangle((20, 51, 44, 55), radius=2, fill="#edf4fb")

        menu = pystray.Menu(
            pystray.MenuItem("Open ScreenShutter", self.tray_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.tray_exit),
        )
        self.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        # Keep the tray event loop independent from Tk and keep it alive while
        # the main window is withdrawn.
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=False)
        self.tray_thread.start()

    def tray_show(self, _icon=None, _item=None):
        self.hotkey_queue.put("show")

    def tray_exit(self, _icon=None, _item=None):
        self.hotkey_queue.put("exit")

    def position_window_at_cursor(self):
        """Center the main window on the monitor containing the mouse cursor."""
        point = POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return
        monitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return

        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        if width <= 1 or height <= 1:
            width, height = 520, 480
        work = info.rcWork
        x = max(work.left, min(point.x - width // 2, work.right - width))
        y = max(work.top, min(point.y - height // 2, work.bottom - height))
        hwnd = user32.GetAncestor(self.root.winfo_id(), 2) or self.root.winfo_id()
        user32.SetWindowPos(hwnd, HWND_TOP, x, y, width, height, SWP_SHOWWINDOW)

    def show_window(self):
        # Restore the real window on the monitor containing the mouse cursor.
        self.root.overrideredirect(False)
        self.root.attributes("-alpha", 1.0)
        self.root.geometry(self.window_geometry)
        self.root.deiconify()
        self.position_window_at_cursor()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        # Keep the Tk window mapped but fully transparent and off-screen.
        # This keeps Tk's event loop alive on Windows while removing the
        # application window from the taskbar; the tray icon remains available.
        self.save_settings()
        self.root.overrideredirect(True)
        self.root.geometry("1x1-100-100")
        self.root.attributes("-alpha", 0.0)
        self.root.update_idletasks()

    def capture_selected_mode(self):
        mode = self.printscreen_mode.get()
        if mode == "Active window":
            self.capture_window()
        elif mode == "Select region":
            self.select_region()
        else:
            self.capture_full()

    def capture_full(self):
        self.root.withdraw()
        self.root.after(250, self._capture_full_delayed)

    def _capture_full_delayed(self):
        try:
            image = ImageGrab.grab(all_screens=True)
            self.finish_capture(image)
        except Exception as exc:
            self.show_window()
            messagebox.showerror("Capture failed", str(exc))

    def capture_window(self):
        self.root.withdraw()
        self.root.after(250, self._capture_window_delayed)

    def _capture_window_delayed(self):
        try:
            hwnd = user32.GetForegroundWindow()
            rect = ctypes.wintypes.RECT()
            if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                raise RuntimeError("Could not determine the active window bounds.")
            image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)
            self.finish_capture(image)
        except Exception as exc:
            self.show_window()
            messagebox.showerror("Capture failed", str(exc))

    def select_region(self):
        self.root.withdraw()
        self.root.after(250, self._open_region_selector)

    def _open_region_selector(self):
        try:
            # Cover the entire Windows virtual desktop, including monitors to
            # the left/above the primary display (which may have negative X/Y).
            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            if vw <= 0 or vh <= 0:
                raise RuntimeError("Could not determine the virtual desktop size.")

            overlay = tk.Toplevel(self.root)
            overlay.withdraw()
            overlay.overrideredirect(True)
            overlay.configure(bg="black")
            overlay.attributes("-alpha", 0.28)
            overlay.attributes("-topmost", True)

            canvas = tk.Canvas(overlay, cursor="cross", bg="black", highlightthickness=0,
                               bd=0, relief="flat")
            canvas.pack(fill="both", expand=True)

            # Position the actual top-level wrapper, not Tk's inner client HWND.
            overlay.update_idletasks()
            hwnd = user32.GetAncestor(overlay.winfo_id(), 2) or overlay.winfo_id()
            if not user32.SetWindowPos(hwnd, HWND_TOPMOST, vx, vy, vw, vh, SWP_SHOWWINDOW):
                raise ctypes.WinError()
            overlay.deiconify()
            overlay.lift()
            overlay.focus_force()
            start = {"x": 0, "y": 0, "rect": None}

            def down(event):
                start["x"], start["y"] = event.x_root, event.y_root
                start["rect"] = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                         outline="#00aaff", width=2)

            def move(event):
                if start["rect"]:
                    x0 = start["x"] - overlay.winfo_rootx()
                    y0 = start["y"] - overlay.winfo_rooty()
                    canvas.coords(start["rect"], x0, y0, event.x, event.y)

            def up(event):
                x1, y1 = start["x"], start["y"]
                x2, y2 = event.x_root, event.y_root
                overlay.destroy()
                left, right = sorted((x1, x2))
                top, bottom = sorted((y1, y2))
                if right - left < 3 or bottom - top < 3:
                    self.show_window()
                    return
                try:
                    self.finish_capture(ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True))
                except Exception as exc:
                    self.show_window()
                    messagebox.showerror("Capture failed", str(exc))

            overlay.bind("<ButtonPress-1>", down)
            overlay.bind("<B1-Motion>", move)
            overlay.bind("<ButtonRelease-1>", up)
            overlay.bind("<Escape>", lambda _e: (overlay.destroy(), self.show_window()))
            overlay.focus_force()
        except Exception as exc:
            self.show_window()
            messagebox.showerror("Selection failed", str(exc))

    def finish_capture(self, image):
        if self.preview_enabled.get():
            self.show_preview(image)
        else:
            self.save_image(image)

    def show_preview(self, image):
        self.root.deiconify()
        self.root.lift()
        preview = tk.Toplevel(self.root)
        preview.title("Screenshot preview")
        preview.transient(self.root)
        preview.geometry("640x480")
        preview.minsize(360, 260)

        from PIL import ImageTk
        display = image.copy()
        display.thumbnail((600, 360))
        photo = ImageTk.PhotoImage(display)
        label = ttk.Label(preview, image=photo)
        label.image = photo
        label.pack(fill="both", expand=True, padx=12, pady=12)

        buttons = ttk.Frame(preview, padding=10)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save screenshot", command=lambda: (self.save_image(image), preview.destroy())).pack(side="right")
        ttk.Button(buttons, text="Discard", command=preview.destroy).pack(side="right", padx=8)

    def save_image(self, image):
        try:
            folder = Path(self.save_dir.get()).expanduser()
            folder.mkdir(parents=True, exist_ok=True)
            fmt = self.image_format.get().upper()
            ext = {"JPEG": ".jpg", "WEBP": ".webp", "PNG": ".png", "BMP": ".bmp", "TIFF": ".tiff"}[fmt]
            path = folder / f"Screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}{ext}"
            output = image
            options = {}
            if fmt == "JPEG":
                output = image.convert("RGB")
                options["quality"] = int(self.quality.get())
            elif fmt == "WEBP":
                options["quality"] = int(self.quality.get())
            output.save(path, format=fmt, **options)
            self.status.set(f"Saved: {path}")
            self.save_settings()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def startup_link(self):
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        return Path(shell.SpecialFolders("Startup")) / "ScreenShutter.lnk"

    def toggle_startup(self):
        try:
            import sys
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            link = self.startup_link()
            if self.startup.get():
                if "__compiled__" in globals():
                    # In Nuitka onefile mode sys.argv[0] is the outer executable
                    # the user launched; sys.executable may refer to its runtime.
                    target = Path(sys.argv[0]).resolve()
                    arguments = "--start-hidden"
                    working_directory = target.parent
                else:
                    target = Path(sys.executable).resolve()
                    script = Path(__file__).resolve()
                    arguments = f'"{script}" --start-hidden'
                    working_directory = script.parent

                link.parent.mkdir(parents=True, exist_ok=True)
                shortcut = shell.CreateShortCut(str(link))
                shortcut.Targetpath = str(target)
                shortcut.Arguments = arguments
                shortcut.WorkingDirectory = str(working_directory)
                shortcut.Description = "ScreenShutter screenshot utility"
                shortcut.Save()
            elif link.exists():
                link.unlink()
            self.save_settings()
        except Exception as exc:
            self.startup.set(False)
            messagebox.showerror(
                "Startup setting failed",
                f"{exc}\n\nInstall pywin32 to manage the startup shortcut."
            )

    def load_settings(self):
        if not self.settings_file.exists():
            return
        try:
            values = {}
            for line in self.settings_file.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key] = value
            self.save_dir.set(values.get("save_dir", self.save_dir.get()))
            self.image_format.set(values.get("format", "PNG"))
            self.quality.set(int(values.get("quality", "90")))
            self.hotkey.set(values.get("hotkey", DEFAULT_HOTKEY))
            self.printscreen_mode.set(values.get("printscreen_mode", "Full screen"))
            self.preview_enabled.set(values.get("preview_enabled", "1") == "1")
            self.startup.set(values.get("startup", "0") == "1")
        except Exception:
            pass

    def save_settings(self):
        data = [
            f"save_dir={self.save_dir.get()}",
            f"format={self.image_format.get()}",
            f"quality={int(self.quality.get())}",
            f"hotkey={self.hotkey.get()}",
            f"printscreen_mode={self.printscreen_mode.get()}",
            f"preview_enabled={1 if self.preview_enabled.get() else 0}",
            f"startup={1 if self.startup.get() else 0}",
        ]
        self.settings_file.write_text("\n".join(data) + "\n", encoding="utf-8")

    def close(self):
        self.save_settings()
        self.hotkey_listener.stop()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.destroy()


def main():
    if os.name != "nt":
        raise SystemExit("ScreenShutter currently supports Windows only.")
    # Per-monitor DPI awareness keeps mouse coordinates, overlays and captures aligned.
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        pass
    import sys
    start_hidden = "--start-hidden" in sys.argv[1:]
    root = tk.Tk()
    if start_hidden:
        root.withdraw()
    app = ScreenShutter(root, start_hidden=start_hidden)
    root.mainloop()


if __name__ == "__main__":
    main()
