"""Shared read-only access to the saved app results."""

from pathlib import Path
import sqlite3


DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "app" / "results.sqlite"


def connect_read_only(path: Path) -> sqlite3.Connection:
    """Open app results with SQLite enforcing read-only access."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist; run .venv/Scripts/python scripts/build_app_db.py first"
        )
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
