"""Analytics module: pure functions over habits and completions.

Every function here is pure: it takes habits and/or completion data as
arguments and returns a computed result. Nothing in this module touches SQLite
or any other I/O. This keeps the analytics trivially testable against fixed,
hand-verified datasets.

Streak logic
------------
A *period* is a single unit of a habit's schedule: a calendar day for daily
habits, an ISO week for weekly habits. A completion is reduced to its period
via :meth:`habit_tracker.models.Habit.period_key`. A *streak* is a run of
consecutive periods that each contain at least one completion.

To decide whether two periods are consecutive, each period is mapped to an
integer ordinal:
  - daily:  the date's proleptic Gregorian ordinal (``date.toordinal()``).
  - weekly: a week ordinal derived from the ISO calendar, so that adjacent ISO
    weeks differ by exactly 1 even across year boundaries.
Consecutive periods have ordinals differing by exactly 1.
"""

from __future__ import annotations

from datetime import date, datetime

from .models import Completion, Habit


# ----------------------------------------------------------------------
# Listing helpers
# ----------------------------------------------------------------------
def list_all_habits(habits: list[Habit]) -> list[Habit]:
    """Return all tracked habits.

    A thin pass-through provided for API completeness and symmetry with
    :func:`list_habits_by_periodicity`.

    Args:
        habits: The habits to return.

    Returns:
        A new list containing the same habits, in the same order.
    """
    return list(habits)


def list_habits_by_periodicity(
    habits: list[Habit], periodicity: str
) -> list[Habit]:
    """Return only the habits with the given periodicity.

    Args:
        habits: The habits to filter.
        periodicity: Either ``"daily"`` or ``"weekly"``.

    Returns:
        A list of habits whose ``periodicity`` matches, preserving order.
    """
    return [habit for habit in habits if habit.periodicity == periodicity]


# ----------------------------------------------------------------------
# Period-ordinal helpers (internal)
# ----------------------------------------------------------------------
def _period_ordinal(habit: Habit, moment: date | datetime) -> int:
    """Map a moment to an integer ordinal for the habit's period.

    Consecutive periods yield consecutive integers (differing by 1), which is
    what makes run-length streak detection possible.

    Args:
        habit: The habit whose periodicity defines the bucketing.
        moment: The ``date`` or ``datetime`` to map.

    Returns:
        An integer ordinal for the period containing ``moment``.
    """
    if isinstance(moment, datetime):
        moment = moment.date()

    if habit.periodicity == "daily":
        return moment.toordinal()

    # weekly: build a monotonic week ordinal from the ISO calendar.
    # ISO years have 52 or 53 weeks; multiplying the year by 53 and adding the
    # week number is NOT guaranteed to make adjacent weeks differ by exactly 1
    # across a year boundary. Instead, anchor on the Monday of the ISO week and
    # take its ordinal divided by 7, which is exact and gap-free.
    iso_year, iso_week, _ = moment.isocalendar()
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    return monday.toordinal() // 7


def _unique_sorted_ordinals(
    habit: Habit, completions: list[Completion]
) -> list[int]:
    """Return the sorted, de-duplicated period ordinals for completions.

    Multiple completions in the same period collapse to a single ordinal, so a
    period counts once toward a streak regardless of how many completions it
    holds.

    Args:
        habit: The habit whose periodicity defines the bucketing.
        completions: The completions to reduce.

    Returns:
        A sorted list of unique period ordinals.
    """
    ordinals = {_period_ordinal(habit, c.completed_at) for c in completions}
    return sorted(ordinals)


# ----------------------------------------------------------------------
# Streak analytics
# ----------------------------------------------------------------------
def longest_streak_for_habit(
    habit: Habit, completions: list[Completion]
) -> int:
    """Return the longest run of consecutive completed periods for a habit.

    The run may occur anywhere in the habit's history. Multiple completions
    within the same period count once.

    Args:
        habit: The habit to analyse.
        completions: The habit's completions. May be empty.

    Returns:
        The length of the longest streak, in periods. ``0`` if there are no
        completions.
    """
    ordinals = _unique_sorted_ordinals(habit, completions)
    if not ordinals:
        return 0

    longest = 1
    current = 1
    for previous, nxt in zip(ordinals, ordinals[1:]):
        if nxt - previous == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def longest_streak_overall(
    habits: list[Habit], completions: list[Completion]
) -> int:
    """Return the longest streak across all habits.

    Completions are matched to habits by ``habit_id``; completions with no
    matching habit are ignored. Each habit's streak uses its own periodicity.

    Args:
        habits: All habits to consider.
        completions: Completions for any of those habits, in any order.

    Returns:
        The single best longest-streak value across all habits. ``0`` if there
        are no habits or no completions.
    """
    if not habits:
        return 0

    by_habit: dict[int, list[Completion]] = {}
    for completion in completions:
        by_habit.setdefault(completion.habit_id, []).append(completion)

    best = 0
    for habit in habits:
        habit_completions = by_habit.get(habit.id, [])
        best = max(best, longest_streak_for_habit(habit, habit_completions))
    return best


# ----------------------------------------------------------------------
# Completion rate
# ----------------------------------------------------------------------
def completion_rate(
    habit: Habit,
    completions: list[Completion],
    as_of: date | datetime | None = None,
) -> float:
    """Return the fraction of expected periods that were completed.

    The expected periods span from the habit's ``created_at`` through
    ``as_of`` (inclusive), counted in the habit's own period units. The rate is
    the number of distinct completed periods divided by the number of expected
    periods.

    Args:
        habit: The habit to analyse.
        completions: The habit's completions. May be empty.
        as_of: The end of the evaluation window. Defaults to the current local
            time when omitted.

    Returns:
        A float in the range ``0.0``–``1.0``. Returns ``0.0`` when the window
        contains no expected periods (e.g. ``as_of`` precedes ``created_at``).
    """
    if as_of is None:
        as_of = datetime.now()

    start_ordinal = _period_ordinal(habit, habit.created_at)
    end_ordinal = _period_ordinal(habit, as_of)

    expected_periods = end_ordinal - start_ordinal + 1
    if expected_periods <= 0:
        return 0.0

    # Count only completed periods that fall within [start, end].
    completed_in_window = {
        ordinal
        for ordinal in _unique_sorted_ordinals(habit, completions)
        if start_ordinal <= ordinal <= end_ordinal
    }
    return len(completed_in_window) / expected_periods
