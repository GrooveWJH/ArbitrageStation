from __future__ import annotations

import asyncio
import os
import sys
import termios
import tty


class KeyboardHotkeyListener:
    def __init__(self, queue: "asyncio.Queue[str]"):
        self._queue = queue
        self._enabled = False
        self._fd: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._old_attrs = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> bool:
        if not sys.stdin.isatty():
            return False
        try:
            self._fd = sys.stdin.fileno()
            self._old_attrs = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
            self._loop = asyncio.get_running_loop()
            self._loop.add_reader(self._fd, self._on_input)
            self._enabled = True
            return True
        except Exception:
            self.stop()
            return False

    def _on_input(self) -> None:
        if self._fd is None:
            return
        try:
            ch = os.read(self._fd, 1).decode("utf-8", errors="ignore")
        except Exception:
            return
        if ch in {"k", "K"}:
            self._queue.put_nowait("hotkey_k")

    def stop(self) -> None:
        if self._fd is not None and self._loop is not None:
            try:
                self._loop.remove_reader(self._fd)
            except Exception:
                pass
        if self._fd is not None and self._old_attrs is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_attrs)
            except Exception:
                pass
        self._enabled = False
        self._fd = None
        self._old_attrs = None
        self._loop = None
