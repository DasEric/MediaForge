"""Command-line argument parsing for the ``mediaforge`` launcher.

The standalone interactive CLI was removed in the WebUI-only refactor; the
only options left configure how the WebUI itself is started (host/port/
browser) plus a debug-logging switch. Parsed once by :func:`parse_args`,
called from :func:`mediaforge.entry.mediaforge` at startup.
"""

import argparse
import logging
import os

from .logger import get_logger

logger = get_logger(__name__)


def parse_args():
    """Parse CLI arguments for launching the WebUI.

    If ``--debug`` is given, also applies it immediately: sets
    ``MEDIAFORGE_DEBUG_MODE``/``MEDIAFORGE_DEBUG_FORCED`` and raises every
    already-created logger to DEBUG, so debug logging is active before the
    WebUI starts rather than waiting for a settings round-trip.

    Returns the parsed ``argparse.Namespace``.
    Used by: :func:`mediaforge.entry.mediaforge`.
    """
    parser = argparse.ArgumentParser(
        prog="mediaforge",
        description=(
            "MediaForge – WebUI mode. "
            "Run 'mediaforge' to start the web interface directly. "
            "The CLI has been removed; all functionality is available via the WebUI."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-wP",
        "--web-port",
        type=int,
        default=8080,
        help="Port for the web UI (default: 8080)",
    )

    parser.add_argument(
        "-wH",
        "--web-host",
        default="127.0.0.1",
        help="Host/IP für die Web-UI (Standard: 127.0.0.1). Für LAN/Docker: 0.0.0.0",
    )

    parser.add_argument(
        "-wN",
        "--no-browser",
        action="store_true",
        help="Don't open the browser automatically when starting the web UI",
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        os.environ["MEDIAFORGE_DEBUG_MODE"] = "1"
        # Marker so the Web UI can show the debug toggle as checked & locked
        # (it was forced via the CLI and can't be changed at runtime).
        os.environ["MEDIAFORGE_DEBUG_FORCED"] = "1"
        logging.getLogger().setLevel(logging.DEBUG)
        for name in logging.Logger.manager.loggerDict:
            logging.getLogger(name).setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    return args
