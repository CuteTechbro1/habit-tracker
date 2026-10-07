"""Tests for the Click CLI using CliRunner.

Each test runs commands against an isolated temporary database file (via the
global ``--db`` option) so no test touches real data. Covers the full command
surface (init, add, remove, complete, list, analyze longest/streak/rate),
friendly output, and graceful error handling.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from habit_tracker.cli import cli


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """A path to a fresh SQLite file inside a per-test temp directory."""
    return str(tmp_path / "test_habits.db")


def _run(runner: CliRunner, db_path: str, *args: str):
    """Invoke the CLI with the test database path prepended."""
    return runner.invoke(cli, ["--db", db_path, *args])


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestInit:
    def test_init_loads_fixtures(self, runner: CliRunner, db_path: str) -> None:
        result = _run(runner, db_path, "init")
        assert result.exit_code == 0
        assert "predefined habits" in result.output

    def test_init_twice_is_safe(self, runner: CliRunner, db_path: str) -> None:
        _run(runner, db_path, "init")
        result = _run(runner, db_path, "init")
        assert result.exit_code == 0
        assert "already contains" in result.output


class TestAdd:
    def test_add_daily(self, runner: CliRunner, db_path: str) -> None:
        result = _run(runner, db_path, "add", "read", "--period", "daily")
        assert result.exit_code == 0
        assert "Added daily habit 'read'" in result.output

    def test_add_with_description(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = _run(
            runner,
            db_path,
            "add",
            "read",
            "--period",
            "daily",
            "--desc",
            "20 minutes",
        )
        assert result.exit_code == 0
        list_result = _run(runner, db_path, "list")
        assert "20 minutes" in list_result.output

    def test_add_duplicate_fails_gracefully(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        result = _run(runner, db_path, "add", "read", "--period", "weekly")
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_add_invalid_period_rejected(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = _run(runner, db_path, "add", "read", "--period", "monthly")
        # Click's Choice validation rejects this before the command body.
        assert result.exit_code != 0


class TestRemove:
    def test_remove_existing(self, runner: CliRunner, db_path: str) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        result = _run(runner, db_path, "remove", "read")
        assert result.exit_code == 0
        assert "Removed habit 'read'" in result.output

    def test_remove_unknown_fails_gracefully(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = _run(runner, db_path, "remove", "nope")
        assert result.exit_code != 0
        assert "No habit named 'nope'" in result.output


class TestComplete:
    def test_complete_with_date(self, runner: CliRunner, db_path: str) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        result = _run(
            runner, db_path, "complete", "read", "--date", "2026-10-01"
        )
        assert result.exit_code == 0
        assert "Completed 'read' for 2026-10-01" in result.output

    def test_complete_default_today(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        result = _run(runner, db_path, "complete", "read")
        assert result.exit_code == 0
        assert "for today" in result.output

    def test_complete_unknown_fails(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = _run(runner, db_path, "complete", "nope")
        assert result.exit_code != 0
        assert "No habit named 'nope'" in result.output

    def test_complete_double_same_day_fails(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        _run(runner, db_path, "complete", "read", "--date", "2026-10-01")
        result = _run(
            runner, db_path, "complete", "read", "--date", "2026-10-01"
        )
        assert result.exit_code != 0
        assert "already completed" in result.output

    def test_complete_bad_date_fails(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        result = _run(
            runner, db_path, "complete", "read", "--date", "not-a-date"
        )
        assert result.exit_code != 0


class TestList:
    def test_list_empty(self, runner: CliRunner, db_path: str) -> None:
        result = _run(runner, db_path, "list")
        assert result.exit_code == 0
        assert "No habits found" in result.output

    def test_list_shows_habits(self, runner: CliRunner, db_path: str) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        _run(runner, db_path, "add", "laundry", "--period", "weekly")
        result = _run(runner, db_path, "list")
        assert "read [daily]" in result.output
        assert "laundry [weekly]" in result.output

    def test_list_filter_by_period(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "add", "read", "--period", "daily")
        _run(runner, db_path, "add", "laundry", "--period", "weekly")
        result = _run(runner, db_path, "list", "--period", "weekly")
        assert "laundry [weekly]" in result.output
        assert "read" not in result.output


class TestAnalyze:
    def test_longest_on_fixtures(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "init")
        result = _run(runner, db_path, "analyze", "longest")
        assert result.exit_code == 0
        # drink_water perfect daily streak = 28.
        assert "28" in result.output

    def test_streak_on_fixture_habit(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "init")
        result = _run(runner, db_path, "analyze", "streak", "drink_water")
        assert result.exit_code == 0
        assert "28 day(s)" in result.output

    def test_streak_weekly_unit(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "init")
        result = _run(runner, db_path, "analyze", "streak", "laundry")
        assert result.exit_code == 0
        assert "week(s)" in result.output

    def test_rate_on_fixture_habit(
        self, runner: CliRunner, db_path: str
    ) -> None:
        _run(runner, db_path, "init")
        result = _run(runner, db_path, "analyze", "rate", "meditate")
        assert result.exit_code == 0
        assert "%" in result.output

    def test_streak_unknown_fails(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = _run(runner, db_path, "analyze", "streak", "nope")
        assert result.exit_code != 0
        assert "No habit named 'nope'" in result.output

    def test_rate_unknown_fails(
        self, runner: CliRunner, db_path: str
    ) -> None:
        result = _run(runner, db_path, "analyze", "rate", "nope")
        assert result.exit_code != 0
        assert "No habit named 'nope'" in result.output
