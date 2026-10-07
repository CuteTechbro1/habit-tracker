"""Database layer: SQLite connection management and schema setup.

This is the lowest layer in the architecture. It owns the raw connection to
SQLite and the schema definition. Nothing above this layer issues DDL; they go
through the Storage layer, which in turn relies on the connection produced here.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Default on-disk location for the database. Tests override this with an
# in-memory database or a temp file via `connect`.
DEFAULT_DB_PATH = Path("data") / "habits.db"

# Schema as defined in the approved technical design.
#
# - Dates are stored as ISO 8601 TEXT (SQLite has no native datetime type).
# - ON DELETE CASCADE removes a habit's completions when the habit is deleted;
#   this requires `PRAGMA foreign_keys = ON` on every connection.
# - UNIQUE on name and CHECK on periodicity push integrity rules into the DB.
SCHEMA = """
CREATE TABLE IF NOT EXISTS habits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    periodicity TEXT    NOT NULL CHECK (periodicity IN ('daily', 'weekly')),
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS completions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id     INTEGER NOT NULL,
    completed_at TEXT    NOT NULL,
    FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_completions_habit ON completions(habit_id);
"""


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection and prepare it for use.

    Pass the sentinel string ``":memory:"`` to create an in-memory database
    (used by tests). For any other path, the parent directory is created if it
    does not already exist.

    The connection is configured with:
      - ``row_factory = sqlite3.Row`` so rows support name-based access.
      - ``PRAGMA foreign_keys = ON`` so ON DELETE CASCADE is enforced.
    """
    if str(db_path) == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create the tables and indexes if they do not already exist.

    Idempotent: safe to call on an existing database thanks to the
    ``IF NOT EXISTS`` clauses in the schema.
    """
    conn.executescript(SCHEMA)
    conn.commit()


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Convenience helper: connect and ensure the schema exists.

    Returns an open, schema-ready connection.
    """
    conn = connect(db_path)
    init_schema(conn)
    return conn
