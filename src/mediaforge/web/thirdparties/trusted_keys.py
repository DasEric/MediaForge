"""The whitelist: whose signature MediaForge believes.

This file is the trust root of the whole module system. A module is "official"
because a key in ``BUILTIN_KEYS`` signed it — not because a store said so, not
because the module's folder is called something official-sounding, and **not
because a user typed a key into a settings field**.

That last part is the point, so it is worth stating plainly: there is no UI for
this list, and there never should be. Trust that an end user can paste in is
trust an attacker can talk them into pasting in — "add this key and my module
will show up as Official" is a one-line social-engineering script, and the whole
badge stops meaning anything the moment it becomes user-configurable. The keys
ship *inside* MediaForge, so the claim "official" is exactly as trustworthy as
the build the user installed, and no more.

Adding a maintainer key here is therefore a code change, reviewed and released
like any other — which is precisely the ceremony it deserves. Generate it with
the store tooling:

    mfstore key gen --name "Your Name" --tiers official,verified
    mfstore key export <key_id> --python     # prints the block to paste below

(The Signing keys page of the module store server prints the same block for its
own key.)

The private half never leaves the machine that generated it, and nothing in
MediaForge can sign anything: this module only ever *verifies*.

A store still cannot promote itself. Pointing MediaForge at a repository changes
nothing about what it trusts — an index.json claiming ``"trust": "official"`` for
a package signed by a key that isn't below is simply wrong, and MediaForge treats
it as unverified. The only way a module is official on a user's machine is that
the shipped build already knew the key that signed it.
"""

from ...logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Maintainer keys. Empty on purpose in this repo: the real ones must be generated
# by the people who will hold the private halves, and pasted in by them. Until one
# is here, *nothing* verifies as official — which is the honest state of affairs,
# not a bug.
#
# Shape (public_key is base64 of the raw 32-byte Ed25519 public key):
#
#     {
#         "key_id": "3f2a9c1d8b4e5a60",
#         "name": "Domekologe",
#         "public_key": "kR2h…",
#         "tiers": ("official", "verified"),
#     },
#
# `tiers` is what a key is *allowed* to assert. A reviewer key that should only be
# able to bless third-party submissions gets ("verified",) and can then not mint an
# official module even if it signs a document claiming that tier — signing.py checks
# the tier against this list, not against the document.
# ---------------------------------------------------------------------------
BUILTIN_KEYS = [
    {
        "key_id": "81303bf87ee5664f",
        "name": "MediaForge Module Store",
        "public_key": "/Xo4+5ayCUwHg4MXbUe4Fbw9TY2WfUonzAisxfcyA1M=",
        "tiers": ("official", "verified",),
    },
]


def trusted_keys() -> dict:
    """Every key this build trusts, keyed by key_id.

    Reads nothing but BUILTIN_KEYS: no settings, no database, no environment. The
    trust root has exactly one source, and it is the source that went through code
    review — see this module's docstring for why a configurable one would be worse
    than useless.
    """
    keys = {}
    for entry in BUILTIN_KEYS:
        key_id = str(entry.get("key_id") or "").strip()
        public_key = str(entry.get("public_key") or "").strip()
        if not key_id or not public_key:
            # A malformed entry is a bug in a code change, so say so loudly rather
            # than silently trusting (or silently not trusting) something.
            logger.error("[Signing] Ignoring malformed BUILTIN_KEYS entry: %r", entry)
            continue
        keys[key_id] = {
            "key_id": key_id,
            "name": str(entry.get("name") or key_id),
            "public_key": public_key,
            "tiers": tuple(entry.get("tiers") or ("verified",)),
        }
    return keys
