import argparse
import logging
import os

from .logger import get_logger

logger = get_logger(__name__)


def parse_args():
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
