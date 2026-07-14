"""Shared language-folder names for MEDIAFORGE_LANG_SEPARATION.

Single source of truth for the mapping between a queue item's language label
and the on-disk subfolder it is downloaded into, plus the list of folders any
"is this already downloaded?" scan has to look inside.

Historically the map lived in queue_worker/autosync_worker while every scanner
(browse, library, search) kept its own hardcoded four-entry list. Anything
downloaded into a folder outside that list — e.g. hanime, which is a single
"Japanese Dub" track — was therefore invisible to the downloaded/"Vorhanden"
detection. Keep both sides here so they cannot drift apart again.
"""

# Language label (as stored on the queue item) -> on-disk folder name.
LANG_FOLDER_MAP = {
    "German Dub": "german-dub",
    "English Sub": "english-sub",
    "German Sub": "german-sub",
    "English Dub": "english-dub",
    "English Dub (German Sub)": "english-dub-german-sub",
    # hanime: Japanese audio with burned-in subtitles — one logical language.
    "Japanese Dub": "japanese-dub",
}

# Every folder a downloaded-detection scan must consider.
LANG_FOLDERS = list(LANG_FOLDER_MAP.values())

# Languages an auto-sync job with "All Languages" should try to fetch. This is
# deliberately NOT every key of LANG_FOLDER_MAP: "Japanese Dub" only exists on
# hanime (which has no other track), so including it here would make every
# regular series sync attempt a language it never has.
SYNC_ALL_LANGUAGES = [
    "German Dub",
    "English Sub",
    "German Sub",
    "English Dub",
    "English Dub (German Sub)",
]


def lang_folder_for(language: str) -> str:
    """Folder name for a language label, with a slugified fallback."""
    return LANG_FOLDER_MAP.get(
        language, (language or "").lower().replace(" ", "-")
    )
