"""Shared per-request helpers extracted from the old create_app() closure.

These used to be nested functions defined inside create_app() that closed
over a local ``auth_enabled`` variable; they are now plain module functions
that read the shared flag from runtime_state instead.
"""
from . import runtime_state


def get_current_user_info():
    """Return (username, is_admin) for the current request.

    When auth is disabled the app treats every request as an admin request.

    Used by: routes/settings.py and routes/syncplay.py (and several other
    route modules) to decide what the current request is allowed to do.
    """
    if not runtime_state.AUTH_ENABLED:
        return None, True  # no auth → treat as admin
    from .auth import get_current_user
    user = get_current_user()
    if not user:
        return None, False
    username = (
        user.get("username")
        if isinstance(user, dict)
        else getattr(user, "username", None)
    )
    role = (
        user.get("role")
        if isinstance(user, dict)
        else getattr(user, "role", "user")
    )
    return username, role == "admin"
