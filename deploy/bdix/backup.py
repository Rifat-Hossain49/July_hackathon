"""Create and integrity-check a non-overwriting online SQLite backup."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3


def backup(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination:
        raise ValueError("source and destination must differ")
    if destination.exists():
        raise FileExistsError(f"backup destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(
            f"backup destination directory does not exist: {destination.parent}"
        )

    source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
            result = destination_connection.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise RuntimeError("backup integrity check failed")
        finally:
            destination_connection.close()
    except Exception:
        if destination.exists():
            destination.unlink()
        raise
    finally:
        source_connection.close()
    os.chmod(destination, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    arguments = parser.parse_args()
    backup(arguments.source, arguments.destination)
    print(f"Verified SQLite backup created: {arguments.destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
