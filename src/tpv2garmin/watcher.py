"""Folder watcher: watchdog + polling fallback for OneDrive reliability."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from tpv2garmin.fixer import get_unprocessed_files

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds


class FitFileHandler(FileSystemEventHandler):
    """Watchdog handler that filters for .fit files."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".fit":
            logger.info("Watchdog detected new file: %s", path.name)
            self._callback(path)


class FolderWatcher:
    """Watches a folder for new .fit files using watchdog + polling fallback."""

    def __init__(self, folder: Path, callback) -> None:
        """
        Args:
            folder: Directory to watch.
            callback: Called with Path for each new .fit file detected.
        """
        self._folder = folder
        self._callback = callback
        self._observer: Observer | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._watching = False

    @property
    def is_watching(self) -> bool:
        return self._watching

    def start(self) -> None:
        """Start watchdog observer and polling thread."""
        if self._watching:
            return

        self._stop_event.clear()
        self._watching = True

        # Watchdog observer
        try:
            self._observer = Observer()
            handler = FitFileHandler(self._callback)
            self._observer.schedule(handler, str(self._folder), recursive=False)
            self._observer.daemon = True
            self._observer.start()
            logger.info("Watchdog started on %s", self._folder)
        except Exception:
            logger.exception("Failed to start watchdog observer")

        # Polling fallback thread
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="fit-poller"
        )
        self._poll_thread.start()
        logger.info("Polling fallback started (every %ds)", POLL_INTERVAL)

    def stop(self) -> None:
        """Stop both the watchdog observer and polling thread."""
        if not self._watching:
            return

        self._stop_event.set()
        self._watching = False

        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                logger.debug("Error stopping watchdog", exc_info=True)
            self._observer = None

        self._poll_thread = None
        logger.info("Folder watcher stopped")

    def restart(self) -> None:
        """Restart the watcher (e.g. after folder path change)."""
        self.stop()
        self.start()

    def _poll_loop(self) -> None:
        """Safety-net polling: scan for unprocessed files every POLL_INTERVAL."""
        while not self._stop_event.is_set():
            self._stop_event.wait(POLL_INTERVAL)
            if self._stop_event.is_set():
                break
            try:
                for path in get_unprocessed_files(self._folder):
                    logger.info("Poller found unprocessed file: %s", path.name)
                    self._callback(path)
            except Exception:
                logger.exception("Error during poll scan")
