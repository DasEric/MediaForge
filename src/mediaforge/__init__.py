"""MediaForge package root.

Importing this package immediately mirrors legacy ``ANIWORLD_*`` environment
variables onto their ``MEDIAFORGE_*`` equivalents (see :mod:`mediaforge.env`),
so any submodule that reads ``os.environ`` afterwards sees the new-style
names even if only the old ones were set (e.g. an existing Docker setup).
"""
# Honour legacy ANIWORLD_* environment variables as a fallback for the
# renamed MEDIAFORGE_* variables, as early as possible on import.
from .env import mirror_legacy_env as _mirror_legacy_env
_mirror_legacy_env()
