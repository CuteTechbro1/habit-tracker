"""Tests for the HabitManager business-logic layer.

Covers periodicity validation, duplicate-name rejection, the
one-completion-per-period rule (daily and weekly), delete behaviour including
cascade of completions, and the read/list operations.
"""

from datetime import datetime

import pytest

from habit_tracker.manager import HabitManager


class TestCreateHabit:
    def test_creates_and_persists(self, manager: HabitManager) -> None:
        habit = manager.create_habit("read", "daily", "read daily")
        assert habit.id is not None
        assert manager.get_habit("read").name == "read"

    def test_invalid_periodicity_raises(self, manager: HabitManager) -> None:
        with pytest.raises(ValueError):
            manager.create_habit("bad", "monthly")

    def test_duplicate_name_raises(self, manager: HabitManager) -> None:
        manager.create_habit("read", "daily")
        with pytest.raises(ValueError):
            manager.create_habit("read", "weekly")


class TestDeleteHabit:
    def test_deletes_habit(self, manager: HabitManager) -> None:
        manager.create_habit("read", "daily")
        manager.delete_habit("read")
        with pytest.raises(ValueError):
            manager.get_habit("read")

    def test_delete_unknown_raises(self, manager: HabitManager) -> None:
        with pytest.raises(ValueError):
            manager.delete_habit("nope")

    def test_delete_removes_completions(self, manager: HabitManager) -> None:
        manager.create_habit("read", "daily")
        manager.complete_habit("read", datetime(2026, 10, 1, 8, 0))
        habit = manager.get_habit("read")
        assert len(manager.storage.get_completions(habit.id)) == 1

        manager.delete_habit("read")
        # Habit is gone; its completions went with it (cascade).
        with pytest.raises(ValueError):
            manager.get_habit("read")


class TestCompleteHabitDaily:
    def test_completes(self, manager: HabitManager) -> None:
        manager.create_habit("read", "daily")
        completion = manager.complete_habit("read", datetime(2026, 10, 1, 8, 0))
        assert completion.id is not None

    def test_unknown_habit_raises(self, manager: HabitManager) -> None:
        with pytest.raises(ValueError):
            manager.complete_habit("nope")

    def test_double_completion_same_day_raises(
        self, manager: HabitManager
    ) -> None:
        manager.create_habit("read", "daily")
        manager.complete_habit("read", datetime(2026, 10, 1, 8, 0))
        # Different time, same calendar day -> rejected.
        with pytest.raises(ValueError):
            manager.complete_habit("read", datetime(2026, 10, 1, 20, 0))

    def test_completion_next_day_allowed(self, manager: HabitManager) -> None:
        manager.create_habit("read", "daily")
        manager.complete_habit("read", datetime(2026, 10, 1, 8, 0))
        # Next day is a new period -> allowed.
        second = manager.complete_habit("read", datetime(2026, 10, 2, 8, 0))
        assert second.id is not None


class TestCompleteHabitWeekly:
    def test_double_completion_same_week_raises(
        self, manager: HabitManager
    ) -> None:
        manager.create_habit("laundry", "weekly")
        # Both dates are in ISO week 41 of 2026 (Mon 5th, Wed 7th).
        manager.complete_habit("laundry", datetime(2026, 10, 5, 8, 0))
        with pytest.raises(ValueError):
            manager.complete_habit("laundry", datetime(2026, 10, 7, 8, 0))

    def test_completion_next_week_allowed(self, manager: HabitManager) -> None:
        manager.create_habit("laundry", "weekly")
        manager.complete_habit("laundry", datetime(2026, 10, 5, 8, 0))
        # Following week is a new period -> allowed.
        second = manager.complete_habit("laundry", datetime(2026, 10, 12, 8, 0))
        assert second.id is not None


class TestQueries:
    def test_get_unknown_raises(self, manager: HabitManager) -> None:
        with pytest.raises(ValueError):
            manager.get_habit("nope")

    def test_list_habits_empty(self, manager: HabitManager) -> None:
        assert manager.list_habits() == []

    def test_list_habits_returns_all(self, manager: HabitManager) -> None:
        manager.create_habit("a", "daily")
        manager.create_habit("b", "weekly")
        assert {h.name for h in manager.list_habits()} == {"a", "b"}

    def test_list_by_periodicity(self, manager: HabitManager) -> None:
        manager.create_habit("a", "daily")
        manager.create_habit("b", "weekly")
        manager.create_habit("c", "daily")
        daily = manager.list_by_periodicity("daily")
        weekly = manager.list_by_periodicity("weekly")
        assert {h.name for h in daily} == {"a", "c"}
        assert {h.name for h in weekly} == {"b"}

    def test_list_by_periodicity_invalid_raises(
        self, manager: HabitManager
    ) -> None:
        with pytest.raises(ValueError):
            manager.list_by_periodicity("monthly")
