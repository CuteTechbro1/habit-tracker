"""Predefined habits and four weeks of fixture completion data.

This module seeds a demo-ready database: five predefined habits plus exactly
four weeks (28 days) of realistic completion data. It is used by ``habit init``
to give a grader an immediately explorable dataset, and the same patterns are
hand-verifiable for analytics.

The dataset is deterministic. All dates are derived from a fixed anchor,
:data:`START_DATE`, which is a Monday so that ISO-week boundaries align cleanly
with the four-week window.

Dataset design
--------------
  - ``drink_water`` (daily)  -- perfect streak: all 28 days completed.
  - ``exercise``    (daily)  -- broken streak: a clean gap mid-window, so the
                                current streak is shorter than the longest.
  - ``read``        (daily)  -- realistic: most days, with scattered misses.
  - ``meditate``    (daily)  -- sparse: roughly half the days.
  - ``laundry``     (weekly) -- perfect weekly streak: once in each of the four
                                ISO weeks.

Together these cover at least one daily and one weekly habit, a perfect streak
(two of them, one daily and one weekly), a broken streak, and a spread of
completion rates suitable for demonstrating every analytics function.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .manager import HabitManager

# Fixed anchor for the four-week window. A Monday, so ISO weeks line up with
# the four 7-day blocks of the dataset.
START_DATE: datetime = datetime(2026, 9, 7, 0, 0, 0)  # Monday, ISO week 37
WINDOW_DAYS: int = 28  # exactly four weeks

# A representative completion time of day, so stored timestamps look realistic.
_COMPLETION_TIME: time = time(8, 0, 0)


@dataclass(frozen=True)
class PredefinedHabit:
    """A predefined habit definition plus the day offsets it was completed on.

    Attributes:
        name: Unique habit name.
        periodicity: Either ``"daily"`` or ``"weekly"``.
        description: Human-readable description.
        completion_offsets: Day offsets (0-based) from :data:`START_DATE` on
            which the habit was completed. For weekly habits, each offset
            should fall in a distinct ISO week.
    """

    name: str
    periodicity: str
    description: str
    completion_offsets: tuple[int, ...]


def _daily_all() -> tuple[int, ...]:
    """Every day of the window (perfect daily streak)."""
    return tuple(range(WINDOW_DAYS))


def _daily_broken() -> tuple[int, ...]:
    """Days 0-9, then a gap (10-13 missing), then 14-27.

    Longest streak is the 14-day tail (days 14..27). The leading run is 10
    days, so the longest streak is clearly the second block and there is an
    obvious break in the middle.
    """
    first_block = tuple(range(0, 10))      # days 0..9  (10 days)
    # days 10,11,12,13 skipped -> the break
    second_block = tuple(range(14, 28))    # days 14..27 (14 days)
    return first_block + second_block


def _daily_realistic() -> tuple[int, ...]:
    """Most days completed, with a handful of scattered single-day misses.

    Misses on days 3, 11, 18, 25 (one per week). Yields a high but imperfect
    completion rate and several short streaks.
    """
    misses = {3, 11, 18, 25}
    return tuple(d for d in range(WINDOW_DAYS) if d not in misses)


def _daily_sparse() -> tuple[int, ...]:
    """Roughly every other day completed (sparse, low streaks)."""
    return tuple(range(0, WINDOW_DAYS, 2))  # 14 days: 0,2,4,...,26


def _weekly_perfect() -> tuple[int, ...]:
    """One completion in each of the four ISO weeks (perfect weekly streak).

    Offsets 0, 7, 14, 21 land on the Monday of each successive week.
    """
    return (0, 7, 14, 21)


# The five predefined habits.
PREDEFINED_HABITS: tuple[PredefinedHabit, ...] = (
    PredefinedHabit(
        name="drink_water",
        periodicity="daily",
        description="Drink 2 litres of water",
        completion_offsets=_daily_all(),
    ),
    PredefinedHabit(
        name="exercise",
        periodicity="daily",
        description="30 minutes of exercise",
        completion_offsets=_daily_broken(),
    ),
    PredefinedHabit(
        name="read",
        periodicity="daily",
        description="Read for 20 minutes",
        completion_offsets=_daily_realistic(),
    ),
    PredefinedHabit(
        name="meditate",
        periodicity="daily",
        description="Meditate for 10 minutes",
        completion_offsets=_daily_sparse(),
    ),
    PredefinedHabit(
        name="laundry",
        periodicity="weekly",
        description="Do the laundry",
        completion_offsets=_weekly_perfect(),
    ),
)


def _offset_to_datetime(offset: int) -> datetime:
    """Convert a day offset from START_DATE into a timestamped datetime.

    Args:
        offset: Number of days after :data:`START_DATE`.

    Returns:
        The datetime at :data:`START_DATE` + ``offset`` days, at the
        representative completion time of day.
    """
    day = (START_DATE + timedelta(days=offset)).date()
    return datetime.combine(day, _COMPLETION_TIME)


def load_fixtures(manager: HabitManager) -> None:
    """Seed the predefined habits and their four weeks of completions.

    Each habit is created with its ``created_at`` set to :data:`START_DATE` so
    completion-rate windows are well defined, then its recorded completions are
    added through the manager (which enforces one-per-period, matching the
    fixture design where no two completions share a period).

    Args:
        manager: The :class:`HabitManager` to seed. Expected to be backed by an
            empty database.

    Raises:
        ValueError: If a predefined habit already exists in the database
            (propagated from the manager's duplicate check).
    """
    for predefined in PREDEFINED_HABITS:
        habit = manager.create_habit(
            name=predefined.name,
            periodicity=predefined.periodicity,
            description=predefined.description,
        )
        # Pin created_at to the window start for deterministic analytics.
        habit.created_at = START_DATE
        assert habit.id is not None
        manager.storage.conn.execute(
            "UPDATE habits SET created_at = ? WHERE id = ?",
            (START_DATE.isoformat(), habit.id),
        )
        manager.storage.conn.commit()

        for offset in predefined.completion_offsets:
            manager.complete_habit(
                predefined.name, _offset_to_datetime(offset)
            )
