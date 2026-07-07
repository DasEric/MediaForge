"""In-memory capture of console output for the optional Web Console.

A lightweight tee is installed over ``sys.stdout`` / ``sys.stderr`` at app
startup. Everything written to the real console (log lines, werkzeug request
logs, plain ``print`` calls, …) is mirrored 1:1 into a bounded, thread-safe
ring buffer that the Web UI can poll read-only.

The buffer keeps the last ``_MAX_LINES`` lines so newly opened consoles can
show recent history instead of an empty screen.
"""

import sys
import threading
from collections import deque

_MAX_LINES = 2000


class _ConsoleBuffer:
    """Thread-safe ring buffer of console lines with monotonic sequence ids."""

    def __init__(self, max_lines: int = _MAX_LINES):
        self._lock = threading.Lock()
        self._lines = deque(maxlen=max_lines)  # entries: (seq:int, text:str)
        self._seq = 0
        self._partial = ""  # trailing text not yet terminated by a newline

    def write(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            buf = self._partial + text
            buf = buf.replace("\r\n", "\n")
            segments = buf.split("\n")
            # The last element is the (possibly empty) unfinished line.
            self._partial = segments.pop()
            for seg in segments:
                # Emulate a terminal carriage-return overwrite: only the text
                # after the last \r on a line is what would remain visible.
                if "\r" in seg:
                    seg = seg.split("\r")[-1]
                self._seq += 1
                self._lines.append((self._seq, seg))
            # Collapse carriage-return overwrites in the still-open partial line
            # too. Progress output (yt-dlp/ffmpeg) emits \r-only updates with no
            # trailing newline; without this the partial buffer would grow
            # without bound and every subsequent write would get O(n²) slower,
            # choking the download thread that writes the progress.
            if "\r" in self._partial:
                self._partial = self._partial.rsplit("\r", 1)[-1]
            if len(self._partial) > 8192:
                self._partial = self._partial[-8192:]

    def get_since(self, after: int = 0) -> dict:
        with self._lock:
            try:
                after = int(after or 0)
            except (TypeError, ValueError):
                after = 0
            new = [(s, t) for (s, t) in self._lines if s > after]
            partial = self._partial.split("\r")[-1] if self._partial else ""
            first_seq = self._lines[0][0] if self._lines else self._seq
            return {
                "lines": [{"seq": s, "text": t} for (s, t) in new],
                "seq": self._seq,
                "partial": partial,
                "first_seq": first_seq,
            }


_buffer = _ConsoleBuffer()


class _Tee:
    """File-like wrapper that writes to the original stream and the buffer."""

    def __init__(self, original):
        self._original = original

    def write(self, text):
        try:
            self._original.write(text)
        except Exception:
            pass
        try:
            _buffer.write(text)
        except Exception:
            pass
        return len(text) if text else 0

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return self._original.isatty()
        except Exception:
            return False

    # Delegate everything else (encoding, fileno, …) to the wrapped stream.
    def __getattr__(self, name):
        return getattr(self._original, name)


_installed = False
_install_lock = threading.Lock()


def _repoint_existing_handlers(orig_stdout, orig_stderr) -> None:
    """Repoint logging StreamHandlers that were bound to the original streams.

    ``logging.StreamHandler`` captures ``sys.stderr`` at construction time, so
    handlers created before the tee was installed (e.g. the ``mediaforge``
    logger built at import time) would otherwise bypass the buffer.
    """
    import logging

    try:
        loggers = [logging.getLogger()]
        loggers += list(logging.Logger.manager.loggerDict.values())
    except Exception:
        return
    for lg in loggers:
        handlers = getattr(lg, "handlers", None)
        if not handlers:
            continue
        for h in handlers:
            stream = getattr(h, "stream", None)
            if stream is orig_stdout:
                h.stream = sys.stdout
            elif stream is orig_stderr:
                h.stream = sys.stderr


def install_capture() -> None:
    """Install the stdout/stderr tee once. Safe to call repeatedly.

    Used by: app.py, called once during create_app() startup.
    """
    global _installed
    with _install_lock:
        if _installed:
            return
        orig_stdout = sys.stdout
        orig_stderr = sys.stderr
        if orig_stdout is not None and not isinstance(orig_stdout, _Tee):
            sys.stdout = _Tee(orig_stdout)
        if orig_stderr is not None and not isinstance(orig_stderr, _Tee):
            sys.stderr = _Tee(orig_stderr)
        _repoint_existing_handlers(orig_stdout, orig_stderr)
        _installed = True


def get_console_output(after: int = 0) -> dict:
    """Return console lines with sequence id greater than after.

    Used by: routes/settings.py's console-polling endpoint.
    """
    return _buffer.get_since(after)
