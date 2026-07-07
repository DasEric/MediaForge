"""Public exports for the ``mediaforge.anime4k`` package.

Re-exports the legacy mpv-config setup entry point from ``anime4k.py``. See
that module for the full shader-download and on-demand upscaling pipeline.
"""

from .anime4k import anime4k

__all__ = ["anime4k"]
