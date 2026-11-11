"""Generic background-thread runner for Qt. Every blocking call (network
requests, file I/O, launching the game and waiting for it to exit) goes
through here instead of running on the UI thread — Qt signals are
thread-safe when the receiver lives on the main thread, which is exactly
how these are always connected.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal

# Every QThread this module starts gets tracked here so the app can wait
# for in-flight work before quitting. Destroying a running QThread crashes
# the process (SIGABRT) — this is what prevents that when someone closes
# the window mid-download or mid-request.
#
# IMPORTANT: only mutate this list from the main thread. QThread.finished
# is emitted from the *worker* thread's context, so a plain lambda
# connected to it runs on that worker thread too (Qt can't determine
# thread affinity for a bare callable — only for a bound method of a
# QObject). TaskRunner/DownloadRunner below are QObject subclasses
# specifically so their cleanup method has main-thread affinity and Qt
# correctly queues it to run there instead of racing on the worker thread.
_active_threads: list[QThread] = []


def _register_thread(thread: QThread) -> None:
    _active_threads.append(thread)


def _unregister_thread(thread: QThread) -> None:
    if thread in _active_threads:
        _active_threads.remove(thread)


def wait_for_all_threads(timeout_ms: int = 8000) -> None:
    """Call this from the app's aboutToQuit handler. Asks every tracked
    thread to stop and waits for it to actually finish — a blocking
    network call won't respond to quit() until it returns naturally, so
    this can legitimately take a moment (the default timeout is set
    comfortably longer than every blocking call's own timeout elsewhere
    in this app, so in normal operation this always succeeds).

    If a thread still hasn't finished after the timeout — a genuinely
    stuck call — merely giving up here is NOT safe: Qt's QThread
    destructor asserts and aborts the process if it runs while the thread
    is still marked running, and that destructor call happens
    automatically during Python's normal interpreter shutdown regardless
    of whether we're the ones waiting on it. The only way to avoid that
    crash in this case is to skip normal shutdown entirely."""
    for thread in list(_active_threads):
        thread.quit()
    for thread in list(_active_threads):
        thread.wait(timeout_ms)

    still_running = [t for t in _active_threads if t.isRunning()]
    if still_running:
        # Force-terminate the process now, before Python's normal
        # finalization gets anywhere near these QThread objects. This
        # skips Python's own cleanup, which is an acceptable trade here —
        # every file write in this app already uses explicit flush/fsync,
        # so there's nothing meaningful left to lose by skipping it.
        os._exit(0)


class _CallableWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as text
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class TaskRunner(QObject):
    """Runs `fn` on a background QThread, then calls `on_success(result)`
    or `on_error(message)` back on the calling (UI) thread.

    Keeps a reference to the thread/worker on the instance so they aren't
    garbage-collected mid-run — hang on to the TaskRunner itself (e.g. as
    `self._runner = TaskRunner(...)`) for the same reason.
    """

    def __init__(
        self,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = _CallableWorker(fn)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        if on_success:
            self._worker.finished.connect(on_success)
        if on_error:
            self._worker.failed.connect(on_error)

        # Bound methods of TaskRunner (a QObject constructed on, and never
        # moved from, the main thread) are correctly queued to the main
        # thread by Qt even though the signal fires from the worker
        # thread — unlike a bare lambda, which would not be.
        self._worker.finished.connect(self._cleanup)
        self._worker.failed.connect(self._cleanup)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        _register_thread(self._thread)

    def _cleanup(self, *_args: Any) -> None:
        self._thread.quit()
        _unregister_thread(self._thread)

    def start(self) -> None:
        self._thread.start()


class _DownloadWorker(QObject):
    finished = Signal()
    failed = Signal(str)
    progress = Signal(int, int, float, float)  # downloaded, total, speed_bps, eta_secs

    def __init__(self, fn: Callable[[Callable], None]) -> None:
        """`fn` must accept a single `on_progress` callback and call it
        with (downloaded, total, speed_bps, eta_secs)."""
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self._fn(lambda d, t, s, e: self.progress.emit(d, t, s, e))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit()


class DownloadRunner(QObject):
    """Same idea as TaskRunner, but for downloads that also stream
    progress updates. `fn` must accept a single positional `on_progress`
    callback argument."""

    def __init__(
        self,
        fn: Callable[[Callable], None],
        on_progress: Callable[[int, int, float, float], None],
        on_success: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = _DownloadWorker(fn)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(on_progress)
        if on_success:
            self._worker.finished.connect(on_success)
        if on_error:
            self._worker.failed.connect(on_error)

        self._worker.finished.connect(self._cleanup)
        self._worker.failed.connect(self._cleanup)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        _register_thread(self._thread)

    def _cleanup(self, *_args: Any) -> None:
        self._thread.quit()
        _unregister_thread(self._thread)

    def start(self) -> None:
        self._thread.start()
