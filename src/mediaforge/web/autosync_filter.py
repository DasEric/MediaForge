"""Per-job AutoSync episode/season filter helpers.

Filter JSON schema (stored in autosync_jobs.episode_filter, may be NULL):

    {
        "mode": "all" | "selected",
        "seasons": { "<season_number>": true | false | "1-12,15" },
        "include_movies": true | false
    }

Semantics
---------
* episode_filter is NULL / empty  -> no filtering at all.  This preserves the
  exact legacy behaviour: every numbered season is synced, while the
  ``are_movies`` collection (aniworld ``/filme``) stays excluded.  s.to specials
  live in ``staffel-0`` which is a normal numbered season and therefore keeps
  syncing as before.

* mode "all"      -> every season is included unless explicitly set to ``false``;
  brand new seasons that appear later are auto-included.
* mode "selected" -> only seasons present in the map are considered; a season set
  to ``true`` is fully included (incl. future episodes), a range string limits it
  to those episodes, ``false`` excludes it.  Seasons not listed are excluded, so
  entirely new seasons are NOT synced until the user opts them in.

Movies / specials (``are_movies`` collection) are controlled solely by
``include_movies`` and are never episode-filtered.
"""

import json
import logging

logger = logging.getLogger(__name__)


def parse_filter(raw):
    """Return a normalised filter dict, or None when no filter applies."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("AutoSync: invalid episode_filter JSON, ignoring: %r", raw)
            return None
    else:
        return None
    if not isinstance(data, dict):
        return None

    mode = data.get("mode", "all")
    if mode not in ("all", "selected"):
        mode = "all"
    seasons_in = data.get("seasons") or {}
    seasons = {}
    if isinstance(seasons_in, dict):
        for k, v in seasons_in.items():
            try:
                key = str(int(k))
            except (ValueError, TypeError):
                continue
            if isinstance(v, bool):
                seasons[key] = v
            elif isinstance(v, str):
                seasons[key] = v.strip()
            elif v is None:
                continue
            else:
                # numbers or anything truthy -> treat as whole-season on
                seasons[key] = bool(v)
    include_movies = bool(data.get("include_movies", False))

    # An "all"-mode filter with no exclusions and no movies is equivalent to no
    # filter -> let callers treat it as legacy behaviour.
    return {"mode": mode, "seasons": seasons, "include_movies": include_movies}


def parse_range(spec):
    """Parse "1-12,15,20-22" into a set of ints. Empty/invalid -> empty set."""
    result = set()
    if not spec or not isinstance(spec, str):
        return result
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                lo_i, hi_i = int(lo), int(hi)
            except ValueError:
                continue
            if lo_i > hi_i:
                lo_i, hi_i = hi_i, lo_i
            result.update(range(lo_i, hi_i + 1))
        else:
            try:
                result.add(int(part))
            except ValueError:
                continue
    return result


def movie_included(flt):
    """Whether the movies/specials collection should be synced."""
    if flt is None:
        return False  # legacy: movies are skipped
    return bool(flt.get("include_movies"))


def episode_included(flt, season_number, episode_number):
    """Decide whether a numbered-season episode passes the filter.

    Movies are handled separately via :func:`movie_included` and must not be
    passed here.
    """
    if flt is None:
        return True  # legacy: sync everything
    try:
        key = str(int(season_number))
    except (ValueError, TypeError):
        return flt.get("mode", "all") == "all"

    entry = flt.get("seasons", {}).get(key, None)
    if entry is None:
        # Season not explicitly listed
        return flt.get("mode", "all") == "all"
    if entry is True:
        return True
    if entry is False:
        return False
    if isinstance(entry, str):
        eps = parse_range(entry)
        if not eps:
            # A listed-but-unparseable range: treat as whole season on to avoid
            # silently dropping everything.
            return True
        try:
            return int(episode_number) in eps
        except (ValueError, TypeError):
            return False
    return bool(entry)
