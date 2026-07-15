#!/usr/bin/env python3
"""Standalone round-trip test for the Full & Selective Backup feature.

Runs entirely against a throw-away config dir / SQLite database (a temp HOME),
so it never touches the real ~/.mediaforge. Verifies:

  * export -> import restores settings and user-data tables,
  * sensitive values are never written to the portable plaintext section,
  * a wrong password is rejected on both preview and import,
  * secrets survive a change of the install key (.flask_secret) -- i.e. they
    are transported via the backup password, then re-encrypted locally,
  * selective import only writes the chosen categories,
  * cache tables are never exported.

Usage:  python tests/backup_roundtrip_test.py
Exit code 0 = all checks passed, 1 = a check failed.
"""

import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    # Redirect the whole MediaForge config dir into a temp HOME *before*
    # importing the package (config.py resolves ~/.mediaforge at import time).
    cfg = tempfile.mkdtemp(prefix="mf_backup_test_")
    os.environ["HOME"] = cfg
    os.environ["USERPROFILE"] = cfg  # Windows equivalent of HOME

    from mediaforge.web import backup, db

    # A per-install secret so at-rest encryption of sensitive settings is active.
    Path(cfg, ".mediaforge").mkdir(parents=True, exist_ok=True)
    Path(cfg, ".mediaforge", ".flask_secret").write_bytes(os.urandom(48))
    db._fernet_instance = None

    db.init_app_settings_db()
    db.init_favourites_db()
    db.init_custom_paths_db()

    # Seed one favourite (schema-agnostic: fill every non-id column).
    conn = db.get_db()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(favourites)").fetchall()]
    row = {c: "test-" + c for c in cols if c != "id"}
    conn.execute(
        f"INSERT INTO favourites ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    conn.commit()
    conn.close()

    db.set_setting("download_path", "/media/library")
    db.set_setting("download_language", "German")
    db.set_setting("seerr_api_key", "SECRET-KEY-123")  # sensitive

    raw = db.get_db().execute(
        "SELECT value FROM app_settings WHERE key='seerr_api_key'"
    ).fetchone()["value"]
    assert raw.startswith("enc:"), "sensitive setting must be encrypted at rest"

    pw = "correct horse battery staple"
    cats = ["settings", "favourites", "custom_paths"]

    blob = backup.export_backup(cats, pw)
    env = json.loads(blob)
    assert env["format"] == "mediaforge-backup"
    assert "SECRET-KEY-123" not in json.dumps(env["data"]), "secret leaked into plaintext!"
    assert "enc:" not in json.dumps(env["data"].get("settings", {})), "enc value in portable data"

    assert backup.preview_backup(blob, "wrong")["password_ok"] is False
    assert backup.preview_backup(blob, pw)["password_ok"] is True

    # Simulate migrating to a *different* installation: rotate the local key.
    Path(cfg, ".mediaforge", ".flask_secret").write_bytes(os.urandom(48))
    db._fernet_instance = None
    c = db.get_db()
    c.execute("DELETE FROM app_settings")
    c.execute("DELETE FROM favourites")
    c.commit()
    c.close()

    try:
        backup.import_backup(blob, "nope", cats, "replace")
        raise AssertionError("wrong-password import should have been rejected")
    except backup.BackupError:
        pass

    report = backup.import_backup(blob, pw, cats, "replace")
    assert db.get_setting("download_path") == "/media/library"
    assert db.get_setting("download_language") == "German"
    assert db.get_setting("seerr_api_key") == "SECRET-KEY-123"
    raw2 = db.get_db().execute(
        "SELECT value FROM app_settings WHERE key='seerr_api_key'"
    ).fetchone()["value"]
    assert raw2.startswith("enc:"), "restored secret must be re-encrypted under the new key"
    assert db.get_db().execute("SELECT COUNT(*) c FROM favourites").fetchone()["c"] >= 1

    # Selective import: only favourites -> settings stay empty.
    c = db.get_db()
    c.execute("DELETE FROM app_settings")
    c.commit()
    c.close()
    backup.import_backup(blob, pw, ["favourites"], "merge")
    assert db.get_setting("download_path") is None, "unselected category must not import"

    # Cache tables are never part of a backup.
    assert "tmdb_cache" not in env["data"]
    assert "browse_cache" not in env["data"]

    print("import report:", report)
    print("ALL BACKUP TESTS PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print("BACKUP TEST FAILED:", exc)
        sys.exit(1)
