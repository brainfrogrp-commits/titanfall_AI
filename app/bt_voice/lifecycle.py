"""Make sure the app dies with its console window, so an orphaned copy can't
keep holding the port and serving an old page."""

import atexit
import os
import signal
import threading
import time

_done = threading.Event()
_keep = []  # the ctypes callback must stay referenced or Windows crashes calling it


def _run_cleanup(cleanup) -> None:
    if _done.is_set():
        return
    _done.set()
    try:
        cleanup()
    except Exception:
        pass


def _parent_alive(original_ppid: int) -> bool:
    if os.name != "nt":
        # on Linux/macOS an orphan is re-parented to init, so the parent id changes
        return os.getppid() == original_ppid
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, original_ppid)
    if not handle:
        return False  # no such process any more
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True  # can't tell; don't kill ourselves by mistake
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def install(cleanup) -> None:
    """Call once at startup. `cleanup` should release the hotkey and mic."""
    atexit.register(_run_cleanup, cleanup)

    def stop(*_args):
        _run_cleanup(cleanup)
        os._exit(0)

    for name in ("SIGTERM", "SIGBREAK"):  # SIGBREAK exists on Windows only
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), stop)
            except (ValueError, OSError):
                pass

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        handler_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def on_console_event(event):
            # 2 = the console window was closed, 5 = logoff, 6 = shutdown
            if event in (2, 5, 6):
                stop()
            return False

        callback = handler_type(on_console_event)
        _keep.append(callback)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(callback, True)

    original_ppid = os.getppid()

    def watch_parent():
        while True:
            time.sleep(2)
            if not _parent_alive(original_ppid):
                stop()

    threading.Thread(target=watch_parent, daemon=True).start()
