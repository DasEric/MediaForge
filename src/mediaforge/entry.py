import sys
import warnings
from pathlib import Path

# authlib internally uses its deprecated jose module — suppress until they fix it
warnings.filterwarnings("ignore", category=DeprecationWarning, module="authlib")
try:
    from authlib.deprecate import AuthlibDeprecationWarning
    warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)
except ImportError:
    pass

from .arguments import parse_args
from .autodeps import ensure_patchright_chromium
from .config import MEDIAFORGE_CONFIG_DIR, VERSION
from .env import merge_env
from .logger import get_logger

merge_env(
    Path(__file__).resolve().parent / ".env.example",
    MEDIAFORGE_CONFIG_DIR / ".env",
)

logger = get_logger(__name__)


def set_terminal_title():
    """Set the terminal title if running in a TTY"""
    if sys.stdout.isatty():
        title = f"MediaForge v.{VERSION}"
        print(f"\033]0;{title}\007", end="", flush=True)


def mediaforge():
    """Main entry point — always starts the WebUI directly."""
    try:
        logger.debug("Starting WebUI...")
        set_terminal_title()
        ensure_patchright_chromium()

        args = parse_args()

        # Seamlessly carry over data from a previous "AniWorld Downloader"
        # install (~/.aniworld) so nobody loses their history/settings on
        # the rename. No-op once the new database exists.
        try:
            from .legacy_import import import_legacy_if_needed
            import_legacy_if_needed()
        except Exception:  # never block startup on an import hiccup
            logger.warning("Legacy data import skipped due to an error", exc_info=True)

        from .web import start_web_ui

        start_web_ui(
            host=args.web_host,
            port=args.web_port,
            open_browser=not args.no_browser,
            auth_enabled=True,
            sso_enabled=False,
            force_sso=False,
        )
        return 0

    except KeyboardInterrupt:
        print("\nQuitting.", file=sys.stderr)
        return 130

    except Exception as err:
        logger.error("Unexpected error occurred", exc_info=True)
        print(f"\nAn unexpected error occurred: {err}", file=sys.stderr)
        print("Please check the logs for more details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(mediaforge())
