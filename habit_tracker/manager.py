"""Business logic layer: HabitManager.

The manager enforces the application's business rules and orchestrates calls to
the Storage layer. It contains no SQL: all persistence goes through
:class:`habit_tracker.storage.Storage`.

Rules enforced here:
  - Periodicity must be valid (delegated to :class:`Habit` construction).
  - Habit names are unique (no duplicates).
  - A habit cannot be completed twice within the same period (same day for
    daily habits, same ISO week for weekly habits).
"""

from __future__ import annotations

from datetime import datetime

from .models import Completion, Habit
from .storage import Storage


class HabitManager:
    """Coordinates habit operations and enforces business rules.

    The manager is the layer the CLI talks to. It validates input, applies
    rules that span more than a single row, and delegates all reads and writes
    to the injected :class:`Storage`.

    Attributes:
        storage: The persistence gateway used for all data access.
    """

    def __init__(self, storage: Storage) -> None:
        """Create a manager backed by a storage instance.

        Args:
            storage: The :class:`Storage` used for persistence.
        """
        self.storage = storage

    def create_habit(
        self, name: str, periodicity: str, description: str = ""
    ) -> Habit:
        """Create and persist a new habit.

        Periodicity is validated by :class:`Habit` construction (which raises
        ``ValueError`` for anything other than ``"daily"`` or ``"weekly"``).
        The name must not already be in use.

        Args:
            name: Unique name for the habit.
            periodicity: Either ``"daily"`` or ``"weekly"``.
            description: Optional free-text description.

        Returns:
            The persisted :class:`Habit` with its ``id`` populated.

        Raises:
            ValueError: If the periodicity is invalid, or if a habit with the
                same name already exists.
        """
        # Constructing the Habit validates periodicity up front.
        habit = Habit(
            name=name, periodicity=periodicity, description=description
        )
        if self.storage.get_habit_by_name(name) is not None:
            raise ValueError(f"A habit named {name!r} already exists.")
        return self.storage.add_habit(habit)

    def delete_habit(self, name: str) -> None:
        """Delete a habit by name, along with its completions.

        Args:
            name: The name of the habit to delete.

        Raises:
            ValueError: If no habit with that name exists.
        """
        habit = self.storage.get_habit_by_name(name)
        if habit is None:
            raise ValueError(f"No habit named {name!r}.")
        assert habit.id is not None  # persisted habits always have an id
        self.storage.remove_habit(habit.id)

    def complete_habit(
        self, name: str, when: datetime | None = None
    ) -> Completion:
        """Mark a habit as completed for a given moment.

        Enforces the one-completion-per-period rule: a daily habit may only be
        completed once per calendar day, a weekly habit once per ISO week. The
        period is derived from :meth:`Habit.period_key`.

        Args:
            name: The name of the habit to complete.
            when: Timestamp of the completion. Defaults to the current local
                time when omitted.

        Returns:
            The persisted :class:`Completion` with its ``id`` populated.

        Raises:
            ValueError: If no habit with that name exists, or if the habit has
                already been completed within the same period.
        """
        habit = self.storage.get_habit_by_name(name)
        if habit is None:
            raise ValueError(f"No habit named {name!r}.")
        assert habit.id is not None

        moment = when if when is not None else datetime.now()
        target_key = habit.period_key(moment)

        existing = self.storage.get_completions(habit.id)
        for completion in existing:
            if habit.period_key(completion.completed_at) == target_key:
                raise ValueError(
                    f"Habit {name!r} already completed for period "
                    f"{target_key!r}."
                )

        return self.storage.add_completion(habit.id, moment)

    def get_habit(self, name: str) -> Habit:
        """Fetch a single habit by name.

        Args:
            name: The name of the habit to retrieve.

        Returns:
            The matching :class:`Habit`.

        Raises:
            ValueError: If no habit with that name exists.
        """
        habit = self.storage.get_habit_by_name(name)
        if habit is None:
            raise ValueError(f"No habit named {name!r}.")
        return habit

    def list_habits(self) -> list[Habit]:
        """Return all tracked habits.

        Returns:
            A list of every :class:`Habit`, ordered as the storage returns
            them. Empty if none exist.
        """
        return self.storage.get_all_habits()

    def list_by_periodicity(self, periodicity: str) -> list[Habit]:
        """Return habits filtered by periodicity.

        Args:
            periodicity: Either ``"daily"`` or ``"weekly"``.

        Returns:
            A list of habits with the given periodicity.

        Raises:
            ValueError: If ``periodicity`` is not a valid value.
        """
        from .models import VALID_PERIODICITIES

        if periodicity not in VALID_PERIODICITIES:
            allowed = ", ".join(sorted(VALID_PERIODICITIES))
            raise ValueError(
                f"Invalid periodicity {periodicity!r}; expected one of: "
                f"{allowed}"
            )
        return [
            habit
            for habit in self.storage.get_all_habits()
            if habit.periodicity == periodicity
        ]
