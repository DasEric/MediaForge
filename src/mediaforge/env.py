"""Environment-variable and ``.env`` file handling.

Two independent jobs live here: (1) mirroring legacy ``ANIWORLD_*``
environment variables onto their ``MEDIAFORGE_*`` equivalents, and (2)
merging a user's existing ``.env`` file against the shipped
``.env.example`` template so new config keys get their defaults while the
user's existing values are preserved.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

# match lines like KEY=VALUE, ignoring comments and blank lines
ENV_LINE_RE = re.compile(r"^([^#\n=]+?)=(.*)$")

# Backwards compatibility: the project was renamed from "AniWorld Downloader"
# to "MediaForge". All configuration variables moved from the ANIWORLD_ prefix
# to MEDIAFORGE_. Old ANIWORLD_ variables are still honoured as a fallback so
# existing .env files, Docker setups and shell exports keep working.
LEGACY_PREFIX = "ANIWORLD_"
NEW_PREFIX = "MEDIAFORGE_"


def mirror_legacy_env():
    """Mirror any legacy ANIWORLD_* variables to their MEDIAFORGE_* counterpart.

    Only fills in a MEDIAFORGE_* value when it is not already set, so an
    explicit new-style variable always wins over the legacy one. Safe to call
    multiple times.
    """
    for key, value in list(os.environ.items()):
        if key.startswith(LEGACY_PREFIX):
            new_key = NEW_PREFIX + key[len(LEGACY_PREFIX):]
            os.environ.setdefault(new_key, value)


def merge_env(example_path: Path, env_path: Path):
    """Merge *env_path* against the *example_path* template, in place.

    For every ``KEY=value`` line in the template, keeps the user's existing
    value from *env_path* if present, otherwise takes the template default.
    Non-key lines (comments/blank lines) are copied through unchanged so the
    template's formatting survives. Does nothing if *env_path* does not
    exist yet (fresh installs are configured entirely through the WebUI).

    Used by: ``entry.py`` and ``config.py``, both called once at import/
    startup time with (``.env.example``, ``~/.mediaforge/.env``).
    """
    # Always mirror legacy variables first so setups that configure everything
    # through the real environment (e.g. Docker) keep working even without a
    # .env file on disk.
    mirror_legacy_env()

    # Only merge if an existing .env is present — never create a new one.
    # New installs configure everything via the WebUI instead.
    if not env_path.exists():
        return
    env_path.parent.mkdir(parents=True, exist_ok=True)
    example_lines = example_path.read_text().splitlines()

    # Load existing values from the user's current .env file
    existing_values = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            m = ENV_LINE_RE.match(line)
            if m:
                k = m.group(1).strip()
                v = m.group(2).strip()
                existing_values[k] = v
                # Legacy alias: a user .env may still use the old ANIWORLD_
                # keys. Map them onto the new MEDIAFORGE_ key so their values
                # survive the merge against the renamed .env.example.
                if k.startswith(LEGACY_PREFIX):
                    existing_values.setdefault(NEW_PREFIX + k[len(LEGACY_PREFIX):], v)

    merged_lines = []
    for line in example_lines:
        m = ENV_LINE_RE.match(line)
        if not m:
            # keep comments, blank lines, formatting exactly
            merged_lines.append(line)
            continue

        key = m.group(1).strip()
        default_value = m.group(2)

        # replace value if user has one
        if key in existing_values:
            merged_lines.append(f"{key}={existing_values[key]}")
        else:
            merged_lines.append(f"{key}={default_value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(merged_lines) + "\n")

    # Load the merged env file, then mirror once more so any values that came
    # in through a legacy .env are also available under MEDIAFORGE_.
    load_dotenv(env_path)
    mirror_legacy_env()
