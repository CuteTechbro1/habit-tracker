# Habit Tracker

A command-line application for tracking daily and weekly habits, built in Python
with a SQLite backend, a Click-based command-line interface, and a dedicated
analytics module for computing streaks and completion rates.

This project was developed as a university coursework submission. It
demonstrates a layered software architecture, separation of concerns, and a
comprehensive automated test suite.

---

## Project Overview

The Habit Tracker allows a user to define habits that recur on either a daily or
weekly schedule, record completions over time, and analyse their consistency
through streak and completion-rate metrics. The application ships with five
predefined habits and four weeks of sample completion data, so its analytics can
be demonstrated immediately after initialisation.

The system is organised into clearly separated layers — domain models,
persistence, business logic, analytics, and presentation — each with a single
responsibility and a one-directional dependency on the layer beneath it. This
structure keeps the codebase testable and the responsibilities isolated.

Key statistics:

- **5 predefined habits** (four daily, one weekly)
- **4 weeks (28 days) of fixture completion data**
- **SQLite** persistence
- **Click** command-line interface
- **107 passing automated tests**

---

## Features

- Create, list, and remove habits with daily or weekly periodicity.
- Record completions on a given date, defaulting to the current day.
- Business rules enforced centrally: unique habit names, valid periodicities,
  and prevention of more than one completion per period.
- Analytics computed as pure functions: longest streak per habit, longest
  streak across all habits, and completion rate.
- A seed command that loads five predefined habits and four weeks of realistic
  sample data for demonstration.
- Graceful, user-friendly error handling at the command-line level.

---

## Architecture

The application follows a layered architecture with strictly one-directional
dependencies. Each layer communicates only with the layer directly beneath it.

```
CLI (cli.py)
   │  parses commands, formats output
   ▼
HabitManager (manager.py)
   │  business rules: create, complete, validate
   ▼
Storage (storage.py)
   │  CRUD against SQLite, maps rows ↔ domain objects
   ▼
Database (db.py)  ── SQLite file
```

The **Analytics** module sits to the side as a collection of pure functions. It
receives habits and completion records as arguments and returns computed
results. It performs no input or output of its own, which makes it trivial to
test against fixed datasets.

| Layer | Module | Responsibility |
|---|---|---|
| Domain | `models.py` | `Habit` and `Completion` entities; period bucketing and validation. |
| Persistence | `db.py`, `storage.py` | Connection and schema setup; CRUD and row-to-object mapping. |
| Business logic | `manager.py` | Validation, uniqueness, one-completion-per-period rule. |
| Analytics | `analytics.py` | Pure functions for streaks and completion rates. |
| Presentation | `cli.py`, `__main__.py` | Command parsing and output formatting. |
| Demo data | `fixtures.py` | Five predefined habits and four weeks of completions. |

The separation ensures, for example, that only the Storage layer is aware that
SQL exists; replacing SQLite with another database would require changes to that
layer alone.

---

## Installation

The project targets **Python 3.14** and depends on **Click**.

Clone or copy the project, then install it in editable mode along with its
dependencies:

```bash
python -m pip install -e .
```

To include the development dependencies (the test runner):

```bash
python -m pip install -e ".[dev]"
```

Installation registers a console script named `habit`. The application can also
be run as a module without installation:

```bash
python -m habit_tracker --help
```

---

## Usage

Initialise the database and load the demonstration data:

```bash
habit init
```

Add a habit, record a completion, and view analytics:

```bash
habit add reading --period daily --desc "Read for 20 minutes"
habit complete reading --date 2026-10-01
habit analyze streak reading
```

A global `--db` option selects the database file (default `data/habits.db`),
which is useful for keeping separate or temporary databases:

```bash
habit --db ./demo.db init
```

---

## CLI Commands

| Command | Description |
|---|---|
| `habit init` | Create the database and load the five predefined habits with four weeks of sample data. Idempotent: does nothing if habits already exist. |
| `habit add NAME --period {daily,weekly} [--desc TEXT]` | Add a new habit. |
| `habit remove NAME` | Remove a habit and its completions. |
| `habit complete NAME [--date YYYY-MM-DD]` | Record a completion; defaults to today. |
| `habit list [--period {daily,weekly}]` | List all habits, optionally filtered by periodicity. |
| `habit analyze longest` | Report the longest streak across all habits. |
| `habit analyze streak NAME` | Report the longest streak for one habit. |
| `habit analyze rate NAME` | Report the completion rate for one habit. |

All commands accept the global `--db PATH` option.

---

## SQLite Storage Design

Data is persisted in two tables. Timestamps are stored as ISO 8601 text, since
SQLite has no native date type; such strings sort chronologically and parse
cleanly back into Python `datetime` objects.

```sql
CREATE TABLE habits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    periodicity TEXT    NOT NULL CHECK (periodicity IN ('daily', 'weekly')),
    created_at  TEXT    NOT NULL
);

CREATE TABLE completions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id     INTEGER NOT NULL,
    completed_at TEXT    NOT NULL,
    FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
);

CREATE INDEX idx_completions_habit ON completions(habit_id);
```

Design decisions:

- The `UNIQUE` constraint on `name` enforces habit-name uniqueness at the
  database level, complementing the check in the business-logic layer.
- The `CHECK` constraint on `periodicity` guards data integrity.
- `ON DELETE CASCADE` ensures that deleting a habit also removes its
  completions. This requires `PRAGMA foreign_keys = ON`, which the connection
  layer enables on every connection.
- Completions store raw timestamps rather than pre-computed periods, keeping the
  stored data flexible; bucketing into periods is performed in the analytics
  layer.

---

## Analytics Functions

All analytics are implemented as pure functions in `analytics.py`. They accept
habits and completion records as arguments and return computed values, with no
database access.

A *period* is the unit of a habit's schedule: a calendar day for daily habits
and an ISO week for weekly habits. Each completion is reduced to a period key,
and periods are mapped to integer ordinals so that consecutive periods differ by
exactly one — including correctly across month and year boundaries. A *streak*
is a run of consecutive completed periods.

| Function | Description |
|---|---|
| `list_all_habits(habits)` | Returns all tracked habits. |
| `list_habits_by_periodicity(habits, periodicity)` | Returns habits filtered by periodicity. |
| `longest_streak_for_habit(habit, completions)` | Longest run of consecutive completed periods for one habit. |
| `longest_streak_overall(habits, completions)` | The best longest-streak value across all habits. |
| `completion_rate(habit, completions, as_of=None)` | Fraction of expected periods completed, in the range 0.0–1.0. |

Multiple completions within the same period count once, so a habit cannot
inflate a streak by being completed several times in a single day or week.

---

## Example Outputs

The following transcript was produced against a freshly initialised database
seeded with the predefined habits and fixture data.

```text
$ habit init
Initialised with 5 predefined habits and four weeks of sample data.

$ habit list
drink_water [daily] - Drink 2 litres of water
exercise [daily] - 30 minutes of exercise
read [daily] - Read for 20 minutes
meditate [daily] - Meditate for 10 minutes
laundry [weekly] - Do the laundry

$ habit analyze longest
Longest streak across all habits: 28 period(s).

$ habit analyze streak drink_water
Longest streak for 'drink_water': 28 day(s).

$ habit analyze streak laundry
Longest streak for 'laundry': 4 week(s).

$ habit analyze rate read
Completion rate for 'read': 80.0%.

$ habit analyze rate meditate
Completion rate for 'meditate': 46.7%.

$ habit list --period weekly
laundry [weekly] - Do the laundry
```

Error handling is explicit and user-friendly:

```text
$ habit complete journal --date 2026-10-01
Completed 'journal' for 2026-10-01.

$ habit complete journal --date 2026-10-01
Error: Habit 'journal' already completed for period '2026-10-01'.

$ habit analyze streak nope
Error: No habit named 'nope'.
```

---

## Testing

The project includes a comprehensive test suite of **107 passing tests**,
executed with `pytest`. Tests use an in-memory or temporary SQLite database so
that no test touches persistent data.

Run the full suite:

```bash
python -m pytest
```

Test coverage by module:

| Test file | Tests | Focus |
|---|---|---|
| `test_models.py` | 16 | Validation, period-key bucketing, due-date logic. |
| `test_storage.py` | 13 | Round-trips, unique-name enforcement, cascade delete. |
| `test_manager.py` | 17 | Business rules: duplicates, double completions, deletion. |
| `test_analytics.py` | 22 | Daily and weekly streaks, overall streak, completion rate, edge cases. |
| `test_fixtures.py` | 17 | Fixture dataset integrity and hand-verified analytics results. |
| `test_cli.py` | 22 | Full command surface via Click's `CliRunner`, including error paths. |
| **Total** | **107** | |

The fixture dataset is designed to exercise every analytics path: it contains a
perfect daily streak (28 days), a perfect weekly streak (4 weeks), a broken
streak with a clear gap, and habits with intermediate completion rates.

---

## Project Structure

```
Habit Tracker/
├── habit_tracker/
│   ├── __init__.py
│   ├── __main__.py          # Enables `python -m habit_tracker`
│   ├── db.py                # Connection management and schema
│   ├── models.py            # Habit and Completion domain entities
│   ├── storage.py           # SQLite persistence and row mapping
│   ├── manager.py           # Business logic (HabitManager)
│   ├── analytics.py         # Pure-function analytics
│   ├── fixtures.py          # Predefined habits and four weeks of data
│   └── cli.py               # Click command-line interface
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared pytest fixtures
│   ├── test_models.py
│   ├── test_storage.py
│   ├── test_manager.py
│   ├── test_analytics.py
│   ├── test_fixtures.py
│   └── test_cli.py
├── pyproject.toml           # Metadata, dependencies, entry point
└── README.md
```

---

## Future Improvements

Several extensions were considered during design and would be natural next
steps:

- **Broken-habit reporting**: an analytics function to list habits whose streak
  has lapsed as of a given date, surfaced through a `habit analyze broken`
  command.
- **Richer reporting**: tabular or chart-based summaries of all habits, and
  per-period history views.
- **Configurable completion time**: recording the time of day of a completion
  rather than a representative fixed time.
- **Export and import**: serialising habits and completions to CSV or JSON for
  backup and portability.
- **Reminders and scheduling**: notifying the user of habits due in the current
  period.
- **Packaging and distribution**: publishing the console script for installation
  from a package index.
