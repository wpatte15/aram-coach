"""Screen capture and a global hotkey, used to read augment choices off the game screen.

The game API does not report augments, so the coach looks at the screen instead. Capture
uses the normal Windows screenshot path and does not touch the game process. It needs League
in Borderless or Windowed mode; exclusive Fullscreen can come back blank.
"""
from __future__ import annotations

import ctypes
import io
import threading
import time
from ctypes import wintypes

from PIL import ImageGrab, ImageStat

_VIRTUAL_KEYS = {f"F{n}": 0x6F + n for n in range(1, 13)}    # F1 = 0x70 ... F12 = 0x7B
_VK_TAB = 0x09


def grab():
    """Capture the primary monitor at full resolution as a PIL image."""
    image = ImageGrab.grab()
    if ImageStat.Stat(image.convert("L")).stddev[0] < 3:
        raise RuntimeError("The screen capture came back blank. Set League to Borderless or Windowed mode.")
    return image


def cursor_position() -> tuple:
    """Mouse position in screen pixels."""
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def tab_is_down() -> bool:
    """True while Tab is held, which is when the in-game scoreboard is showing."""
    return bool(ctypes.windll.user32.GetAsyncKeyState(_VK_TAB) & 0x8000)


def league_in_front() -> bool:
    """True when the League game window has focus, so a screenshot shows the game."""
    user32 = ctypes.windll.user32
    title = ctypes.create_unicode_buffer(128)
    user32.GetWindowTextW(user32.GetForegroundWindow(), title, 128)
    return title.value.startswith("League of Legends (TM) Client")


def to_jpeg(image, max_side: int = 1568, quality: int = 82) -> bytes:
    """JPEG bytes for sending to Claude, scaled down so the longest side is max_side."""
    small = image.copy()
    small.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    small.convert("RGB").save(buffer, "JPEG", quality=quality)
    return buffer.getvalue()


def watch_keys(hotkey: str, on_hotkey, on_tab_held, hold_seconds: float = 0.35) -> bool:
    """Watch two keys by polling their state, which works while the game has focus.

    hotkey: key name, F1 to F12. `on_hotkey` is called once per press.
    on_tab_held: called once each time Tab has been held for `hold_seconds`, which is when
      the in-game scoreboard is on screen.

    Returns False when the hotkey name is unknown. Polling is used because a registered
    system hotkey did not fire in a real game: another program already held F9. Polling
    reads only these two keys and does not stop them reaching the game.
    """
    code = _VIRTUAL_KEYS.get(hotkey.upper())
    if code is None:
        return False

    def loop():
        user32 = ctypes.windll.user32
        down = lambda vk: bool(user32.GetAsyncKeyState(vk) & 0x8000)
        hotkey_was_down, tab_since, tab_fired = False, None, False
        while True:
            pressed = down(code)
            if pressed and not hotkey_was_down:
                on_hotkey()
            hotkey_was_down = pressed

            if down(_VK_TAB):
                tab_since = tab_since or time.time()
                if not tab_fired and time.time() - tab_since >= hold_seconds:
                    tab_fired = True
                    on_tab_held()
            else:
                tab_since, tab_fired = None, False
            time.sleep(0.03)

    threading.Thread(target=loop, name="keys", daemon=True).start()
    return True
