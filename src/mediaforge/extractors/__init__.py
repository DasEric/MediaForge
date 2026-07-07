"""Extractor auto-discovery and dispatch registry.

Every module under ``extractors/provider/`` implements one hoster (VOE,
Filemoon, Vidoza, ...) and exposes plain functions named
``get_direct_link_from_<provider>`` and/or ``get_preview_image_link_from_<provider>``.
On import, this package scans all modules in ``provider/`` and collects every
such function into the ``provider_functions`` dict, keyed by function name.

Model code (e.g. episode/movie classes) never imports a specific provider
module directly for this lookup; instead it picks the hoster the site
offered (e.g. "VOE", "Vidmoly") and looks up
``provider_functions[f"get_direct_link_from_{provider.lower()}"]`` to get the
right extractor function at runtime. This lets new provider modules be added
without touching any dispatch code.
"""
import importlib
import inspect
import pkgutil
from pathlib import Path

from ..logger import get_logger

logger = get_logger(__name__)

provider_functions = {}

provider_path = Path(__path__[0]) / "provider"

for _, module_name, _ in pkgutil.iter_modules([str(provider_path)]):
    try:
        mod = importlib.import_module(f".provider.{module_name}", __name__)
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith(("get_direct_link_from_", "get_preview_image_link_from_")):
                provider_functions[name] = obj
    except Exception as e:
        logger.warning(f"Failed to load provider module '{module_name}': {e}")

# Example usage:
# provider_functions["get_direct_link_from_voe"](url)
#
# Used by: models/s_to/episode.py, models/filmpalast_to/episode.py,
# models/aniworld_to/episode.py, models/megakino_to/episode.py and
# models/megakino_to/movie.py (all via provider_functions[...] lookup keyed
# on the episode/movie's selected_provider).
