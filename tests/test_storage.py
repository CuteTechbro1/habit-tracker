"""Tests for the Storage layer.

Covers round-trips (write then read back), row-to-object mapping with datetime
parsing, unique-name enforcement at the DB level, and cascade delete of
completions when a habit is removed.
"""

from datetime import datetime

import sqlite3

import pytest

from habit_tracker.models import Completion, Habit
from habit_tracker.storage import Storage


class TestAddHabit:
    def test_returns_habit_with_id(self, storage: Storage) -> None:
        habit = Habit(name="read", periodicity="daily", description="read daily")
        saved = storage.add_habit(habit)
        assert saved.id is not None
        assert saved.name == "read"
        assert saved.description == "read daily"
        assert saved.periodicity == "daily"

    def test_duplicate_name_rejected_by_db(self, storage: Storage) -> None:
        storage.add_habit(Habit(name="read", periodicity="daily"))
        with pytest.raises(sqlite3.IntegrityError):
            storage.add_habit(Habit(name="read", periodicity="weekly"))


class TestGetHabitByName:
    def test_round_trip_preserves_fields(self, storage: Storage) -> None:
        created = datetime(2026, 10, 1, 9, 30)
        storage.add_habit(
            Habit(
                name="meditate",
                periodicity="daily",
                description="10 minutes",
                created_at=created,
            )
        )
        fetched = storage.get_habit_by_name("meditate")
        assert fetched is not None
        assert fetched.name == "meditate"
        assert fetched.description == "10 minutes"
        assert fetched.periodicity == "daily"
        # created_at round-trips through ISO 8601 back into a datetime.
        assert fetched.created_at == created
        assert isinstance(fetched.created_at, datetime)

    def test_missing_returns_none(self, storage: Storage) -> None:
        assert storage.get_habit_by_name("nope") is None


class TestGetAllHabits:
    def test_empty(self, storage: Storage) -> None:
        assert storage.get_all_habits() == []

    def test_returns_all_ordered_by_id(self, storage: Storage) -> None:
        storage.add_habit(Habit(name="a", periodicity="daily"))
        storage.add_habit(Habit(name="b", periodicity="weekly"))
        storage.add_habit(Habit(name="c", periodicity="daily"))
        habits = storage.get_all_habits()
        assert [h.name for h in habits] == ["a", "b", "c"]
        assert all(isinstance(h, Habit) for h in habits)


class TestRemoveHabit:
    def test_removes_habit(self, storage: Storage) -> None:
        saved = storage.add_habit(Habit(name="read", periodicity="daily"))
        storage.remove_habit(saved.id)
        assert storage.get_habit_by_name("read") is None

    def test_remove_nonexistent_is_noop(self, storage: Storage) -> None:
        # Should not raise.
        storage.remove_habit(999)

    def test_cascade_deletes_completions(self, storage: Storage) -> None:
        saved = storage.add_habit(Habit(name="read", periodicity="daily"))
        storage.add_completion(saved.id, datetime(2026, 10, 1, 8, 0))
        storage.add_completion(saved.id, datetime(2026, 10, 2, 8, 0))
        assert len(storage.get_completions(saved.id)) == 2

        storage.remove_habit(saved.id)
        assert storage.get_completions(saved.id) == []


class TestCompletions:
    def test_add_completion_returns_with_id(self, storage: Storage) -> None:
        saved = storage.add_habit(Habit(name="read", periodicity="daily"))
        when = datetime(2026, 10, 1, 8, 0)
        completion = storage.add_completion(saved.id, when)
        assert completion.id is not None
        assert completion.habit_id == saved.id
        assert completion.completed_at == when

    def test_add_completion_defaults_to_now(self, storage: Storage) -> None:
        saved = storage.add_habit(Habit(name="read", periodicity="daily"))
        before = datetime.now()
        completion = storage.add_completion(saved.id)
        assert completion.completed_at >= before

    def test_get_completions_ordered_ascending(self, storage: Storage) -> None:
        saved = storage.add_habit(Habit(name="read", periodicity="daily"))
        storage.add_completion(saved.id, datetime(2026, 10, 3, 8, 0))
        storage.add_completion(saved.id, datetime(2026, 10, 1, 8, 0))
        storage.add_completion(saved.id, datetime(2026, 10, 2, 8, 0))
        completions = storage.get_completions(saved.id)
        times = [c.completed_at for c in completions]
        assert times == sorted(times)
        assert all(isinstance(c, Completion) for c in completions)

    def test_get_completions_empty(self, storage: Storage) -> None:
        saved = storage.add_habit(Habit(name="read", periodicity="daily"))
        assert storage.get_completions(saved.id) == []
