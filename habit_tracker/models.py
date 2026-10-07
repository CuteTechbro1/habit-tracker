"""Domain models for the Habit Tracker.

This module defines the core domain entities, ``Habit`` and ``Completion``.
They carry no persistence knowledge: a model knows its own properties and can
answer questions about itself (e.g. which period a date falls in, whether the
habit is due on a given date). All SQL lives in the Storage layer, which maps
database rows to and from these objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

# The only two periodicities the system supports, as fixed in the approved
# design. Centralised here so validation and the CHECK constraint stay aligned.
VALID_PERIODICITIES: frozenset[str] = frozenset({"daily", "weekly"})


@dataclass
class Habit:
    """A tracked habit.

    A habit represents something the user intends to do on a recurring
    schedule, either every day (``"daily"``) or every ISO week (``"weekly"``).

    Attributes:
        name: Human-readable, unique identifier for the habit.
        periodicity: Either ``"daily"`` or ``"weekly"``. Validated on
            construction.
        description: Optional free-text description. Defaults to an empty
            string.
        created_at: When the habit started being tracked. Defaults to the
            current local time at construction. Used by analytics as the start
            of the expected-period range.
        id: Database primary key. ``None`` until the habit has been persisted
            by the Storage layer.

    Raises:
        ValueError: If ``periodicity`` is not one of the valid values.
    """

    name: str
    periodicity: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate invariants after dataclass initialisation.

        Raises:
            ValueError: If ``periodicity`` is not ``"daily"`` or ``"weekly"``.
        """
        if self.periodicity not in VALID_PERIODICITIES:
            allowed = ", ".join(sorted(VALID_PERIODICITIES))
            raise ValueError(
                f"Invalid periodicity {self.periodicity!r}; "
                f"expected one of: {allowed}"
            )

    def period_key(self, a_date: date | datetime) -> str:
        """Return the canonical period bucket for a date.

        Completions are grouped by this key so streak and completion-rate math
        can treat each period as a single unit regardless of how many
        completions fall inside it.

        For daily habits the key is the ISO date (``"YYYY-MM-DD"``). For weekly
        habits it is the ISO year-week (``"YYYY-Www"``), e.g. ``"2026-W41"``,
        which groups all days of the same ISO week together and handles
        year boundaries correctly.

        Args:
            a_date: A ``date`` or ``datetime`` to bucket. ``datetime`` values
                are reduced to their date component.

        Returns:
            The canonical period-key string for this habit's periodicity.
        """
        if isinstance(a_date, datetime):
            a_date = a_date.date()

        if self.periodicity == "daily":
            return a_date.isoformat()

        # weekly: ISO year and week number, zero-padded (e.g. "2026-W41").
        iso_year, iso_week, _ = a_date.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    def is_due(self, on_date: date | datetime) -> bool:
        """Report whether the habit is active (being tracked) on a given date.

        A habit is considered due on any date on or after the date it was
        created. Because a daily habit is due every day and a weekly habit is
        due every week, the meaningful question for both is simply whether the
        habit had started being tracked by ``on_date``.

        Args:
            on_date: The ``date`` or ``datetime`` to test.

        Returns:
            ``True`` if ``on_date`` is on or after the habit's creation date,
            otherwise ``False``.
        """
        if isinstance(on_date, datetime):
            on_date = on_date.date()
        return on_date >= self.created_at.date()


@dataclass
class Completion:
    """A single recorded completion of a habit.

    Completions store the raw timestamp of when a habit was marked done. They
    are intentionally not pre-bucketed into periods; bucketing happens in the
    analytics layer via :meth:`Habit.period_key`, which keeps the stored data
    flexible.

    Attributes:
        habit_id: Foreign key to the owning habit's ``id``.
        completed_at: When the habit was completed. Defaults to the current
            local time at construction.
        id: Database primary key. ``None`` until persisted by the Storage
            layer.
    """

    habit_id: int
    completed_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None
