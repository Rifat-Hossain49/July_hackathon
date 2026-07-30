from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from deploy.bdix.backup import backup


def test_online_backup_is_integrity_checked_and_never_overwritten(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backup.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE evidence (code TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES (?)", ("CAPSULE_ACCEPTED",))

    backup(source, destination)
    with sqlite3.connect(destination) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT code FROM evidence").fetchone() == (
            "CAPSULE_ACCEPTED",
        )

    with pytest.raises(FileExistsError):
        backup(source, destination)
