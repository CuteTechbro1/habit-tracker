"""Tests for the domain models (``Habit`` and ``Completion``).

Covers periodicity validation, ``period_key`` bucketing for daily and weekly
habits (including year boundaries), and ``is_due``.
"""

from datetime import date, datetime

import pytest

from habit_tracker.models import Completion, Habit


class TestHabitValidation:
    def test_valid_daily(self) -> None:
        habit = Habit(name="read", periodicity="daily")
        assert habit.periodicity == "daily"

    def test_valid_weekly(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly")
        assert habit.periodicity == "weekly"

    def test_invalid_periodicity_raises(self) -> None:
        with pytest.raises(ValueError):
            Habit(name="bad", periodicity="monthly")

    def test_defaults(self) -> None:
        habit = Habit(name="read", periodicity="daily")
        assert habit.description == ""
        assert habit.id is None
        assert isinstance(habit.created_at, datetime)


class TestPeriodKey:
    def test_daily_key_is_iso_date(self) -> None:
        habit = Habit(name="read", periodicity="daily")
        assert habit.period_key(date(2026, 10, 6)) == "2026-10-06"

    def test_daily_key_accepts_datetime(self) -> None:
        habit = Habit(name="read", periodicity="daily")
        assert habit.period_key(datetime(2026, 10, 6, 8, 30)) == "2026-10-06"

    def test_weekly_key_is_iso_year_week(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly")
        # 2026-10-06 falls in ISO week 41.
        assert habit.period_key(date(2026, 10, 6)) == "2026-W41"

    def test_weekly_key_same_week_days_match(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly")
        # Monday and Sunday of the same ISO week share a key.
        monday = date(2026, 10, 5)
        sunday = date(2026, 10, 11)
        assert habit.period_key(monday) == habit.period_key(sunday)

    def test_weekly_key_zero_padded(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly")
        # Early-January date lands in week 1, must be padded to "W01".
        assert habit.period_key(date(2026, 1, 1)) == "2026-W01"

    def test_weekly_key_year_boundary(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly")
        # 2020-12-31 belongs to ISO week 53 of 2020.
        assert habit.period_key(date(2020, 12, 31)) == "2020-W53"


class TestIsDue:
    def test_due_on_creation_date(self) -> None:
        habit = Habit(
            name="read", periodicity="daily", created_at=datetime(2026, 10, 1)
        )
        assert habit.is_due(date(2026, 10, 1)) is True

    def test_due_after_creation(self) -> None:
        habit = Habit(
            name="read", periodicity="daily", created_at=datetime(2026, 10, 1)
        )
        assert habit.is_due(date(2026, 10, 15)) is True

    def test_not_due_before_creation(self) -> None:
        habit = Habit(
            name="read", periodicity="daily", created_at=datetime(2026, 10, 10)
        )
        assert habit.is_due(date(2026, 10, 1)) is False

    def test_accepts_datetime(self) -> None:
        habit = Habit(
            name="read", periodicity="daily", created_at=datetime(2026, 10, 1)
        )
        assert habit.is_due(datetime(2026, 10, 5, 23, 59)) is True


class TestCompletion:
    def test_defaults(self) -> None:
        completion = Completion(habit_id=1)
        assert completion.habit_id == 1
        assert completion.id is None
        assert isinstance(completion.completed_at, datetime)

    def test_explicit_values(self) -> None:
        when = datetime(2026, 10, 1, 8, 0)
        completion = Completion(habit_id=5, completed_at=when, id=3)
        assert completion.habit_id == 5
        assert completion.completed_at == when
        assert completion.id == 3
