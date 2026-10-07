"""Tests for the analytics module.

All analytics are pure functions over in-memory habits and completions, so
these tests build fixed datasets with hand-verified expected values. Covers
daily and weekly streak logic, longest-streak-across-all, completion rate, and
edge cases (no completions, single completion, mid-streak gaps, duplicate
completions within a period, year boundaries).
"""

from datetime import date, datetime

from habit_tracker import analytics
from habit_tracker.models import Completion, Habit


def _completions(habit_id: int, moments: list[datetime]) -> list[Completion]:
    """Build a list of Completion objects for the given moments."""
    return [Completion(habit_id=habit_id, completed_at=m) for m in moments]


class TestListing:
    def test_list_all_returns_copy(self) -> None:
        habits = [Habit(name="a", periodicity="daily")]
        result = analytics.list_all_habits(habits)
        assert result == habits
        assert result is not habits  # new list

    def test_list_by_periodicity(self) -> None:
        habits = [
            Habit(name="a", periodicity="daily"),
            Habit(name="b", periodicity="weekly"),
            Habit(name="c", periodicity="daily"),
        ]
        daily = analytics.list_habits_by_periodicity(habits, "daily")
        weekly = analytics.list_habits_by_periodicity(habits, "weekly")
        assert [h.name for h in daily] == ["a", "c"]
        assert [h.name for h in weekly] == ["b"]


class TestLongestStreakDaily:
    def test_no_completions_is_zero(self) -> None:
        habit = Habit(name="read", periodicity="daily", id=1)
        assert analytics.longest_streak_for_habit(habit, []) == 0

    def test_single_completion_is_one(self) -> None:
        habit = Habit(name="read", periodicity="daily", id=1)
        comps = _completions(1, [datetime(2026, 10, 1, 8, 0)])
        assert analytics.longest_streak_for_habit(habit, comps) == 1

    def test_consecutive_days(self) -> None:
        habit = Habit(name="read", periodicity="daily", id=1)
        comps = _completions(
            1,
            [
                datetime(2026, 10, 1),
                datetime(2026, 10, 2),
                datetime(2026, 10, 3),
                datetime(2026, 10, 4),
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 4

    def test_gap_breaks_streak(self) -> None:
        habit = Habit(name="read", periodicity="daily", id=1)
        # 1,2,3  then gap  then 6,7 -> longest run is 3.
        comps = _completions(
            1,
            [
                datetime(2026, 10, 1),
                datetime(2026, 10, 2),
                datetime(2026, 10, 3),
                datetime(2026, 10, 6),
                datetime(2026, 10, 7),
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 3

    def test_duplicate_in_same_day_counts_once(self) -> None:
        habit = Habit(name="read", periodicity="daily", id=1)
        comps = _completions(
            1,
            [
                datetime(2026, 10, 1, 8, 0),
                datetime(2026, 10, 1, 20, 0),  # same day
                datetime(2026, 10, 2, 8, 0),
            ],
        )
        # Two distinct periods -> streak of 2, not 3.
        assert analytics.longest_streak_for_habit(habit, comps) == 2

    def test_unordered_input(self) -> None:
        habit = Habit(name="read", periodicity="daily", id=1)
        comps = _completions(
            1,
            [
                datetime(2026, 10, 3),
                datetime(2026, 10, 1),
                datetime(2026, 10, 2),
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 3

    def test_month_boundary(self) -> None:
        habit = Habit(name="read", periodicity="daily", id=1)
        comps = _completions(
            1,
            [
                datetime(2026, 10, 30),
                datetime(2026, 10, 31),
                datetime(2026, 11, 1),
                datetime(2026, 11, 2),
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 4


class TestLongestStreakWeekly:
    def test_consecutive_weeks(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly", id=1)
        # One completion in each of three consecutive ISO weeks.
        comps = _completions(
            1,
            [
                datetime(2026, 10, 5),   # week 41
                datetime(2026, 10, 12),  # week 42
                datetime(2026, 10, 19),  # week 43
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 3

    def test_multiple_in_same_week_count_once(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly", id=1)
        comps = _completions(
            1,
            [
                datetime(2026, 10, 5),   # week 41 (Mon)
                datetime(2026, 10, 8),   # week 41 (Thu)
                datetime(2026, 10, 12),  # week 42
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 2

    def test_gap_breaks_weekly_streak(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly", id=1)
        comps = _completions(
            1,
            [
                datetime(2026, 10, 5),   # week 41
                datetime(2026, 10, 12),  # week 42
                # skip week 43
                datetime(2026, 10, 26),  # week 44
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 2

    def test_weekly_year_boundary(self) -> None:
        habit = Habit(name="laundry", periodicity="weekly", id=1)
        # 2020-12-28 is ISO week 53 of 2020; 2021-01-04 is ISO week 1 of 2021.
        # These are consecutive ISO weeks and must form a streak of 2.
        comps = _completions(
            1,
            [
                datetime(2020, 12, 28),  # 2020-W53
                datetime(2021, 1, 4),    # 2021-W01
            ],
        )
        assert analytics.longest_streak_for_habit(habit, comps) == 2


class TestLongestStreakOverall:
    def test_no_habits_is_zero(self) -> None:
        assert analytics.longest_streak_overall([], []) == 0

    def test_picks_best_across_habits(self) -> None:
        h1 = Habit(name="read", periodicity="daily", id=1)
        h2 = Habit(name="laundry", periodicity="weekly", id=2)
        comps = (
            # h1: 2-day streak
            _completions(1, [datetime(2026, 10, 1), datetime(2026, 10, 2)])
            # h2: 3-week streak
            + _completions(
                2,
                [
                    datetime(2026, 10, 5),
                    datetime(2026, 10, 12),
                    datetime(2026, 10, 19),
                ],
            )
        )
        assert analytics.longest_streak_overall([h1, h2], comps) == 3

    def test_ignores_unmatched_completions(self) -> None:
        h1 = Habit(name="read", periodicity="daily", id=1)
        # Completions for a habit id (99) not in the list are ignored.
        comps = _completions(99, [datetime(2026, 10, 1), datetime(2026, 10, 2)])
        assert analytics.longest_streak_overall([h1], comps) == 0


class TestCompletionRate:
    def test_perfect_rate(self) -> None:
        habit = Habit(
            name="read",
            periodicity="daily",
            id=1,
            created_at=datetime(2026, 10, 1),
        )
        comps = _completions(
            1,
            [
                datetime(2026, 10, 1),
                datetime(2026, 10, 2),
                datetime(2026, 10, 3),
            ],
        )
        rate = analytics.completion_rate(habit, comps, as_of=date(2026, 10, 3))
        assert rate == 1.0

    def test_half_rate(self) -> None:
        habit = Habit(
            name="read",
            periodicity="daily",
            id=1,
            created_at=datetime(2026, 10, 1),
        )
        # 2 of 4 expected days completed.
        comps = _completions(
            1, [datetime(2026, 10, 1), datetime(2026, 10, 3)]
        )
        rate = analytics.completion_rate(habit, comps, as_of=date(2026, 10, 4))
        assert rate == 0.5

    def test_no_completions_is_zero(self) -> None:
        habit = Habit(
            name="read",
            periodicity="daily",
            id=1,
            created_at=datetime(2026, 10, 1),
        )
        rate = analytics.completion_rate(habit, [], as_of=date(2026, 10, 10))
        assert rate == 0.0

    def test_as_of_before_creation_is_zero(self) -> None:
        habit = Habit(
            name="read",
            periodicity="daily",
            id=1,
            created_at=datetime(2026, 10, 10),
        )
        rate = analytics.completion_rate(habit, [], as_of=date(2026, 10, 1))
        assert rate == 0.0

    def test_weekly_rate(self) -> None:
        habit = Habit(
            name="laundry",
            periodicity="weekly",
            id=1,
            created_at=datetime(2026, 10, 5),  # week 41
        )
        # Expected weeks 41,42,43 (as_of in week 43). Completed 41 and 43.
        comps = _completions(
            1, [datetime(2026, 10, 5), datetime(2026, 10, 19)]
        )
        rate = analytics.completion_rate(habit, comps, as_of=date(2026, 10, 19))
        assert rate == 2 / 3

    def test_completions_outside_window_excluded(self) -> None:
        habit = Habit(
            name="read",
            periodicity="daily",
            id=1,
            created_at=datetime(2026, 10, 2),
        )
        # One completion before created_at window start -> excluded.
        comps = _completions(
            1,
            [
                datetime(2026, 10, 1),  # before window
                datetime(2026, 10, 2),
                datetime(2026, 10, 3),
            ],
        )
        rate = analytics.completion_rate(habit, comps, as_of=date(2026, 10, 3))
        # Window is 2..3 -> 2 expected, 2 completed in-window -> 1.0
        assert rate == 1.0
