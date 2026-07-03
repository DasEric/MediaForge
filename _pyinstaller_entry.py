"""
PyInstaller entry point — uses absolute imports instead of the
relative imports in src/aniworld/__main__.py.
"""
import sys
from mediaforge.entry import mediaforge

sys.exit(mediaforge())
