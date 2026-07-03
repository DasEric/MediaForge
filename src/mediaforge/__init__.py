"""MediaForge package."""
# Honour legacy ANIWORLD_* environment variables as a fallback for the
# renamed MEDIAFORGE_* variables, as early as possible on import.
from .env import mirror_legacy_env as _mirror_legacy_env
_mirror_legacy_env()
