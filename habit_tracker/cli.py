"""Command-line interface for the Habit Tracker.

Built with Click. This layer is intentionally thin: it parses commands,
delegates all work to :class:`habit_tracker.manager.HabitManager`, and formats
the results for the user. It never touches the Storage layer or SQL directly.

Errors raised by the manager (``ValueError`` for unknown habits, duplicates,
invalid periodicity, double completions) are caught and re-surfaced as clean
Click error messages rather than tracebacks.
"""

from __future__ import annotations

from datetime import datetime

import click

from . import analytics, db
from .fixtures import load_fixtures
from .manager import HabitManager
from .storage import Storage

# Context key under which the shared manager is stored.
_MANAGER_KEY = "manager"


def _build_manager(db_path: str) -> HabitManager:
    """Create a HabitManager backed by a schema-ready database connection.

    Args:
        db_path: Filesystem path to the SQLite database (or ``":memory:"``).

    Returns:
        A ready-to-use :class:`HabitManager`.
    """
    conn = db.init_db(db_path)
    return HabitManager(Storage(conn))


def _parse_date(value: str) -> datetime:
    """Parse a ``YYYY-MM-DD`` string into a datetime, or raise a Click error.

    Args:
        value: The date string from the command line.

    Returns:
        A ``datetime`` at midnight on the given date.

    Raises:
        click.BadParameter: If the string is not a valid ``YYYY-MM-DD`` date.
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise click.BadParameter(
            f"{value!r} is not a valid date; expected YYYY-MM-DD."
        )


@click.group()
@click.option(
    "--db",
    "db_path",
    default=str(db.DEFAULT_DB_PATH),
    show_default=True,
    help="Path to the SQLite database file.",
)
@click.pass_context
def cli(ctx: click.Context, db_path: str) -> None:
    """Habit Tracker: track daily and weekly habits from the command line."""
    ctx.ensure_object(dict)
    ctx.obj[_MANAGER_KEY] = _build_manager(db_path)


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialise the database and load the predefined demo habits."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    if manager.list_habits():
        click.echo("Database already contains habits; nothing to load.")
        return
    load_fixtures(manager)
    click.echo(
        f"Initialised with {len(manager.list_habits())} predefined habits "
        "and four weeks of sample data."
    )


@cli.command()
@click.argument("name")
@click.option(
    "--period",
    "periodicity",
    type=click.Choice(["daily", "weekly"]),
    required=True,
    help="How often the habit recurs.",
)
@click.option("--desc", "description", default="", help="Optional description.")
@click.pass_context
def add(
    ctx: click.Context, name: str, periodicity: str, description: str
) -> None:
    """Add a new habit called NAME."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    try:
        manager.create_habit(name, periodicity, description)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Added {periodicity} habit {name!r}.")


@cli.command()
@click.argument("name")
@click.pass_context
def remove(ctx: click.Context, name: str) -> None:
    """Remove the habit called NAME and its completions."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    try:
        manager.delete_habit(name)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Removed habit {name!r}.")


@cli.command()
@click.argument("name")
@click.option(
    "--date",
    "date_str",
    default=None,
    help="Completion date (YYYY-MM-DD). Defaults to today.",
)
@click.pass_context
def complete(ctx: click.Context, name: str, date_str: str | None) -> None:
    """Mark the habit called NAME as completed."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    when = _parse_date(date_str) if date_str is not None else None
    try:
        manager.complete_habit(name, when)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    label = date_str if date_str is not None else "today"
    click.echo(f"Completed {name!r} for {label}.")


@cli.command(name="list")
@click.option(
    "--period",
    "periodicity",
    type=click.Choice(["daily", "weekly"]),
    default=None,
    help="Filter by periodicity.",
)
@click.pass_context
def list_cmd(ctx: click.Context, periodicity: str | None) -> None:
    """List tracked habits, optionally filtered by periodicity."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    if periodicity is not None:
        habits = manager.list_by_periodicity(periodicity)
    else:
        habits = manager.list_habits()

    if not habits:
        click.echo("No habits found.")
        return

    for habit in habits:
        desc = f" - {habit.description}" if habit.description else ""
        click.echo(f"{habit.name} [{habit.periodicity}]{desc}")


@cli.group()
def analyze() -> None:
    """Analytics commands for streaks and completion rates."""


@analyze.command()
@click.pass_context
def longest(ctx: click.Context) -> None:
    """Show the longest streak across all habits."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    habits = manager.list_habits()
    completions = [
        completion
        for habit in habits
        for completion in manager.storage.get_completions(habit.id)
    ]
    best = analytics.longest_streak_overall(habits, completions)
    click.echo(f"Longest streak across all habits: {best} period(s).")


@analyze.command()
@click.argument("name")
@click.pass_context
def streak(ctx: click.Context, name: str) -> None:
    """Show the longest streak for the habit called NAME."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    try:
        habit = manager.get_habit(name)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    completions = manager.storage.get_completions(habit.id)
    value = analytics.longest_streak_for_habit(habit, completions)
    unit = "day" if habit.periodicity == "daily" else "week"
    click.echo(f"Longest streak for {name!r}: {value} {unit}(s).")


@analyze.command()
@click.argument("name")
@click.pass_context
def rate(ctx: click.Context, name: str) -> None:
    """Show the completion rate for the habit called NAME."""
    manager: HabitManager = ctx.obj[_MANAGER_KEY]
    try:
        habit = manager.get_habit(name)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    completions = manager.storage.get_completions(habit.id)
    value = analytics.completion_rate(habit, completions)
    click.echo(f"Completion rate for {name!r}: {value * 100:.1f}%.")


def main() -> None:
    """Entry point for the ``habit`` console script."""
    cli(obj={})


if __name__ == "__main__":
    main()
