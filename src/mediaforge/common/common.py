"""Generic shared helpers used across the MediaForge codebase.

Currently: fetching GitHub release metadata/asset URLs, and extracting
downloaded .zip/.7z archives. Not to be confused with
``mediaforge.models.common.common``, the unrelated download/encode pipeline
module.
"""

import re
import subprocess
import sys
from pathlib import Path

try:
    from ..config import GLOBAL_SESSION
except ImportError:
    from mediaforge.config import GLOBAL_SESSION


def get_latest_github_release(repo):
    """
    Fetch the latest release tag of a GitHub repository.

    Args:
        repo: GitHub repo in "owner/repo" format, e.g. "shinchiro/mpv-winbuild-cmake"

    Returns:
        The tag name of the latest release

    Used by: fetch_github_asset_urls() (below) and
    mediaforge.anime4k.anime4k.get_anime4k_urls().
    """
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    resp = GLOBAL_SESSION.get(api_url)
    resp.raise_for_status()
    release_data = resp.json()
    return release_data.get("tag_name")


def fetch_github_asset_urls(repo, asset_patterns, release="latest"):
    """
    Fetch all download URLs of GitHub release assets matching one or more regex patterns.

    Args:
        repo: GitHub repo in "owner/repo" format, e.g. "shinchiro/mpv-winbuild-cmake"
        asset_patterns: Regex pattern(s) to match asset file names
        release: Release tag or "latest" (default)

    Returns:
        List of URLs matching any of the patterns (empty list if none found)

    Used by: mediaforge.autodeps (fetching mpv/ffmpeg portable builds).
    """
    if isinstance(asset_patterns, str):
        asset_patterns = [asset_patterns]

    if release == "latest":
        release = get_latest_github_release(repo)

    api_url = f"https://api.github.com/repos/{repo}/releases/tags/{release}"
    resp = GLOBAL_SESSION.get(api_url)
    resp.raise_for_status()
    assets = resp.json().get("assets", [])

    matched_urls = []

    for pattern_str in asset_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        for asset in assets:
            url = asset.get("browser_download_url")
            if url and pattern.search(url):
                matched_urls.append(url)

    return matched_urls


def unzip(file_path, target_dir):
    """Extract a .zip or .7z archive into *target_dir*.

    Uses the system ``unzip``/``7z`` binaries on macOS/Linux. Windows
    extraction is not yet implemented (see TODOs below).

    Used by: mediaforge.anime4k.anime4k.extract_anime4k().
    """
    file_path = Path(file_path)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if file_path.suffix.lower() == ".zip":
        if sys.platform.startswith("win"):
            # TODO: implement
            pass
        else:
            # Use system unzip on macOS/Linux
            print(f"Extracting ZIP: {file_path} -> {target_dir}")
            subprocess.run(
                ["unzip", "-o", str(file_path), "-d", str(target_dir)], check=True
            )
    elif file_path.suffix.lower() == ".7z":
        # use 7z
        if sys.platform.startswith("win"):
            # TODO: implement
            pass
        else:
            # Use system 7z on macOS/Linux
            print(f"Extracting 7z: {file_path} -> {target_dir}")
            subprocess.run(
                ["7z", "x", str(file_path), f"-o{str(target_dir)}"], check=True
            )
    else:
        raise ValueError(f"Unsupported archive format: {file_path}")
