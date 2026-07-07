"""Entry point for ``python -m mediaforge``.

Delegates to :func:`mediaforge.entry.mediaforge`, the same function used by
the installed ``mediaforge`` console script (see ``pyproject.toml``).
"""

import sys

from .entry import mediaforge

sys.exit(mediaforge())
