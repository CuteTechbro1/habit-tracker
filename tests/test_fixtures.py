"""Tests for the predefined habits and four weeks of fixture data.

Verifies the dataset meets every stated requirement (five habits, at least one
daily and one weekly, exactly four weeks of data, a perfect streak, a broken
streak) and that analytics produce the hand-verified expected results on it.
"""

from datetime import timedelta

from habit_tracker import analytics, fixtures
from habit_tracker.manager import HabitManager

_LAST_DAY = fixtures.START_DATE + timedelta(days=fixtures.WINDOW_DAYS - 1)


class TestPredefinedDefinitions:
    def test_five_habits(self) -> None:
        assert len(fixtures.PREDEFINED_HABITS) == 5

    def test_has_daily_and_weekly(self) -> None:
        periods = {h.periodicity for h in fixtures.PREDEFINED_HABITS}
        assert "daily" in periods
        assert "weekly" in periods

    def test_window_is_four_weeks(self) -> None:
        assert fixtures.WINDOW_DAYS == 28

    def test_all_offsets_within_window(self) -> None:
        for habit in fixtures.PREDEFINED_HABITS:
            for offset in habit.completion_offsets:
                assert 0 <= offset < fixtures.WINDOW_DAYS

    def test_names_unique(self) -> None:
        names = [h.name for h in fixtures.PREDEFINED_HABITS]
        assert len(names) == len(set(names))

    def test_perfect_daily_has_all_days(self) -> None:
        water = next(
            h for h in fixtures.PREDEFINED_HABITS if h.name == "drink_water"
        )
        assert len(water.completion_offsets) == 28

    def test_broken_daily_has_a_gap(self) -> None:
        exercise = next(
            h for h in fixtures.PREDEFINED_HABITS if h.name == "exercise"
        )
        offsets = sorted(exercise.completion_offsets)
        # There is at least one gap larger than 1 day somewhere.
        gaps = [b - a for a, b in zip(offsets, offsets[1:])]
        assert any(gap > 1 for gap in gaps)


class TestLoadFixtures:
    def test_loads_five_habits(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        assert len(manager.list_habits()) == 5

    def test_completions_counts(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        for predefined in fixtures.PREDEFINED_HABITS:
            habit = manager.get_habit(predefined.name)
            stored = manager.storage.get_completions(habit.id)
            assert len(stored) == len(predefined.completion_offsets)

    def test_created_at_pinned_to_start(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        for predefined in fixtures.PREDEFINED_HABITS:
            habit = manager.get_habit(predefined.name)
            assert habit.created_at == fixtures.START_DATE


class TestAnalyticsOnFixtures:
    def test_perfect_daily_streak(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        habit = manager.get_habit("drink_water")
        comps = manager.storage.get_completions(habit.id)
        assert analytics.longest_streak_for_habit(habit, comps) == 28

    def test_perfect_daily_rate(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        habit = manager.get_habit("drink_water")
        comps = manager.storage.get_completions(habit.id)
        assert analytics.completion_rate(habit, comps, as_of=_LAST_DAY) == 1.0

    def test_broken_daily_streak(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        habit = manager.get_habit("exercise")
        comps = manager.storage.get_completions(habit.id)
        # Design: 10-day block, gap, then 14-day block -> longest is 14.
        assert analytics.longest_streak_for_habit(habit, comps) == 14

    def test_perfect_weekly_streak(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        habit = manager.get_habit("laundry")
        comps = manager.storage.get_completions(habit.id)
        # Four consecutive ISO weeks.
        assert analytics.longest_streak_for_habit(habit, comps) == 4

    def test_longest_streak_overall_is_perfect_daily(
        self, manager: HabitManager
    ) -> None:
        fixtures.load_fixtures(manager)
        habits = manager.list_habits()
        all_comps = [
            c
            for h in habits
            for c in manager.storage.get_completions(h.id)
        ]
        # drink_water's 28-day streak dominates everything else.
        assert analytics.longest_streak_overall(habits, all_comps) == 28

    def test_realistic_rate_below_one(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        habit = manager.get_habit("read")
        comps = manager.storage.get_completions(habit.id)
        rate = analytics.completion_rate(habit, comps, as_of=_LAST_DAY)
        # 24 of 28 days (4 misses) -> 24/28.
        assert rate == 24 / 28

    def test_sparse_rate_is_half(self, manager: HabitManager) -> None:
        fixtures.load_fixtures(manager)
        habit = manager.get_habit("meditate")
        comps = manager.storage.get_completions(habit.id)
        rate = analytics.completion_rate(habit, comps, as_of=_LAST_DAY)
        # 14 of 28 days -> 0.5.
        assert rate == 0.5
