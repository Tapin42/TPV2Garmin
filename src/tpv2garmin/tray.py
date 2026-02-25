"""System tray icon module using pystray and Pillow."""

import threading
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem, Menu

logger = logging.getLogger(__name__)

ICON_PATH = Path(__file__).parent / "assets" / "icon.ico"


class TrayManager:
    """Manages a system-tray icon with menu actions.

    Parameters
    ----------
    on_open : callable
        Callback invoked when the user clicks *Open*.
    on_process_now : callable
        Callback invoked when the user clicks *Process Now*.
    on_toggle_watching : callable
        Callback invoked when the user clicks *Start/Stop Watching*.
    on_quit : callable
        Callback invoked when the user clicks *Quit*.
    """

    def __init__(self, on_open, on_process_now, on_toggle_watching, on_quit):
        self._on_open = on_open
        self._on_process_now = on_process_now
        self._on_toggle_watching = on_toggle_watching
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create the tray icon and run it on a daemon thread."""
        image = self._create_icon()
        menu = self._build_menu()
        self._icon = pystray.Icon("TPV2Garmin", image, "TPV2Garmin", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("System tray icon started.")

    def stop(self) -> None:
        """Stop the tray icon (and its background thread)."""
        if self._icon is not None:
            self._icon.stop()
            logger.info("System tray icon stopped.")

    def update_title(self, text: str) -> None:
        """Update the icon hover/tooltip text."""
        if self._icon is not None:
            self._icon.title = text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_icon() -> Image.Image:
        """Load the icon from *assets/icon.ico*, or generate a fallback."""
        if ICON_PATH.exists():
            try:
                img = Image.open(ICON_PATH)
                logger.debug("Loaded tray icon from %s", ICON_PATH)
                return img
            except Exception:
                logger.warning(
                    "Failed to open %s; falling back to generated icon.",
                    ICON_PATH,
                    exc_info=True,
                )

        # Fallback: 64x64 blue square with a white "G".
        img = Image.new("RGB", (64, 64), color=(41, 98, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except OSError:
            font = ImageFont.load_default()
        draw.text((16, 8), "G", fill="white", font=font)
        logger.debug("Using generated fallback tray icon.")
        return img

    def _build_menu(self) -> Menu:
        """Build and return the right-click context menu."""
        return Menu(
            MenuItem("Open", self._on_open),
            MenuItem("Process Now", self._on_process_now),
            Menu.SEPARATOR,
            MenuItem("Start/Stop Watching", self._on_toggle_watching),
            Menu.SEPARATOR,
            MenuItem("Quit", self._on_quit),
        )
