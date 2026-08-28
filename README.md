# Library Management System

A type-safe library management system built in Python, using abstract base
classes and dataclasses to model a real library's catalog, members, and
loans. Fully annotated and verified with `mypy --strict` — zero external
dependencies.

## What it does

The system models the core workflow of a physical library:

- A **catalog** of items (books, DVDs, magazines) that can be checked out
- A **membership roll** tracking who's allowed to borrow and how much they
  currently have out
- **Loans** that link an item to a member, with automatic due-date
  calculation and late-fee tracking

Each item type behaves differently — a DVD has a shorter loan period and a
steeper late fee than a book — without any `if isinstance(...)` branching
anywhere in the checkout logic. That behavior lives on the item itself.

## How it works

**Abstract base + subclasses.** `LibraryItem` is an `ABC` that defines two
abstract methods every catalog item must implement: `loan_period_days()` and
`daily_late_fee()`. `Book`, `DVD`, and `Magazine` each implement these with
their own values and add their own fields (`isbn`/`pages`,
`runtime_minutes`, `issue_number`).

**Dataclasses for records.** `Member` and `Loan` are plain dataclasses —
they're just structured data with a couple of helper methods
(`has_capacity()`, `is_returned()`, `days_late()`).

**Library as orchestrator.** The `Library` class owns three internal
dictionaries (catalog, members, loans) and exposes the actual operations:
`add_item`, `register_member`, `checkout_item`, `return_item`,
`available_items`. It calls `item.loan_period_days()` and
`item.daily_late_fee()` polymorphically, so adding a new item type later
means writing one new subclass — no changes to `Library` itself.

**Typed errors.** A small exception hierarchy (`LibraryError` and three
subclasses) reports problems like a missing item, a missing member, or an
item that's already checked out, each carrying the relevant ID so calling
code can handle it programmatically rather than parsing a message string.

## Class overview

| Class | Kind | Purpose |
|---|---|---|
| `ItemStatus`, `MemberType` | Enum | Closed sets of states |
| `LibraryItem` | ABC + dataclass | Shared fields/behavior for all catalog items |
| `Book`, `DVD`, `Magazine` | dataclass | Concrete item types with their own loan rules |
| `Member` | dataclass | A library patron and what they've borrowed |
| `Loan` | dataclass | A single checkout/return transaction |
| `Library` | class | Orchestrates the catalog, members, and loans |
| `LibraryError` + subclasses | Exception | Typed error handling |

## Requirements

- Python 3.10+ (uses `kw_only=True` in dataclasses)
- No third-party dependencies

## Usage

Run the built-in demo, which checks out a book, returns it late, and prints
the resulting fee:

```bash
python3 library_system.py
```

Or use it as a module in your own code:

```python
from datetime import timedelta
from library_system import Library, Book, DVD, Member

library = Library("Riverside Public Library")

library.add_item(
    Book(item_id="B001", title="Dune", creator="Frank Herbert", isbn="9780441013593", pages=412)
)
library.add_item(
    DVD(item_id="D001", title="Arrival", creator="Denis Villeneuve", runtime_minutes=116)
)

library.register_member(Member(member_id="U001", name="Ada Lovelace", email="ada@example.com"))

# Check out a book
loan = library.checkout_item("B001", "U001")
print(loan.due_date)

# Return it a few days late and see the fee
fee = library.return_item(loan.loan_id, return_date=loan.due_date + timedelta(days=3))
print(f"Late fee: ${fee:.2f}")

# See what's still on the shelf
for item in library.available_items():
    print(item.describe())
```

## Type checking

The whole module passes `mypy --strict` with no issues:

```bash
pip install mypy
mypy --strict library_system.py
```

## Extending it

To add a new item type (e.g. an audiobook), subclass `LibraryItem`,
implement `loan_period_days()` and `daily_late_fee()`, and add any
type-specific fields. Nothing in `Library` needs to change.
