"""Shared pytest fixtures.

Provides a fresh in-memory SQLite database per test, plus a Storage bound to
it, so no test touches real data and every test starts from a clean schema.
"""

import sqlite3

import pytest

from habit_tracker import db
from habit_tracker.manager import HabitManager
from habit_tracker.storage import Storage


@pytest.fixture
def connection() -> sqlite3.Connection:
    """A fresh in-memory SQLite connection with the schema applied.

    Yielded per test and closed on teardown.
    """
    conn = db.init_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def storage(connection: sqlite3.Connection) -> Storage:
    """A :class:`Storage` bound to the per-test in-memory connection."""
    return Storage(connection)


@pytest.fixture
def manager(storage: Storage) -> HabitManager:
    """A :class:`HabitManager` bound to the per-test storage."""
    return HabitManager(storage)
