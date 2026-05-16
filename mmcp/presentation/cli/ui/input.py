"""Cross-platform keyboard input handling for the stateful CLI TUI."""

from __future__ import annotations

import os
import sys


def _read_tui_key() -> str:
    """Cross-platform blocking key reader for stateful menu navigation."""
    try:
        if os.name == "nt":
            import msvcrt

            char = msvcrt.getch()
            if char in (b"\xe0", b"\x00"):
                char = msvcrt.getch()
                if char == b"H":
                    return "up"
                if char == b"P":
                    return "down"
                if char == b"K":
                    return "left"
                if char == b"M":
                    return "right"
                if char == b"I":
                    return "pgup"
                if char == b"Q":
                    return "pgdn"
                return ""
            if char == b"\r":
                return "enter"
            if char == b"\x1b":
                return "esc"
            return char.decode("utf-8", errors="ignore").lower()

        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1)
            if char in ("\r", "\n"):
                return "enter"
            if char == "\x1b":
                next1 = sys.stdin.read(1)
                if next1 != "[":
                    return "esc"
                next2 = sys.stdin.read(1)
                if next2 == "A":
                    return "up"
                if next2 == "B":
                    return "down"
                if next2 == "C":
                    return "right"
                if next2 == "D":
                    return "left"
                if next2 == "5":
                    sys.stdin.read(1)
                    return "pgup"
                if next2 == "6":
                    sys.stdin.read(1)
                    return "pgdn"
                return ""
            return char.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        return ""


def _read_scroll_key() -> str:
    """Cross-platform blocking keypress reader for scrollable screens."""
    try:
        if os.name == "nt":
            import msvcrt

            char = msvcrt.getch()
            if char in (b"\xe0", b"\x00"):
                char = msvcrt.getch()
                if char == b"H":
                    return "up"
                if char == b"P":
                    return "down"
                if char == b"I":
                    return "pgup"
                if char == b"Q":
                    return "pgdn"
                return ""
            return char.decode("utf-8").lower()
        else:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                char = sys.stdin.read(1)
                if char == "\x1b":
                    next1 = sys.stdin.read(1)
                    if next1 != "[":
                        return "\x1b"
                    next2 = sys.stdin.read(1)
                    if next2 == "A":
                        return "up"
                    if next2 == "B":
                        return "down"
                    if next2 == "5":
                        sys.stdin.read(1)
                        return "pgup"
                    if next2 == "6":
                        sys.stdin.read(1)
                        return "pgdn"
                return char.lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        return ""
