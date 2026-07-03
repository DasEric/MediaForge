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
