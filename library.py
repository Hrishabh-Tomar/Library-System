"""
Library Management System
==========================

A small but realistic domain model demonstrating:
- Abstract base classes (ABC) for polymorphic catalog items
- Dataclasses for value-heavy / record-like classes
- Enums for closed sets of states
- Custom exception hierarchy
- Full type annotations (mypy clean)

Classes
-------
1. ItemStatus        (Enum)
2. MemberType         (Enum)
3. LibraryItem        (ABC, dataclass)  - abstract base for catalog items
4. Book               (dataclass, concrete LibraryItem)
5. DVD                (dataclass, concrete LibraryItem)
6. Magazine           (dataclass, concrete LibraryItem)
7. Member             (dataclass)
8. Loan               (dataclass)
9. Library            (plain class - orchestrates everything)
   + LibraryError / ItemNotFoundError / MemberNotFoundError / ItemNotAvailableError
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum, auto
from typing import Optional


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------


class ItemStatus(Enum):
    AVAILABLE = auto()
    CHECKED_OUT = auto()
    LOST = auto()
    IN_REPAIR = auto()


class MemberType(Enum):
    STANDARD = auto()
    STUDENT = auto()
    SENIOR = auto()


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------


class LibraryError(Exception):
    """Base class for all library-domain errors."""


class ItemNotFoundError(LibraryError):
    def __init__(self, item_id: str) -> None:
        super().__init__(f"No catalog item with id {item_id!r}")
        self.item_id = item_id


class MemberNotFoundError(LibraryError):
    def __init__(self, member_id: str) -> None:
        super().__init__(f"No member with id {member_id!r}")
        self.member_id = member_id


class ItemNotAvailableError(LibraryError):
    def __init__(self, item_id: str, status: ItemStatus) -> None:
        super().__init__(f"Item {item_id!r} is not available (status={status.name})")
        self.item_id = item_id
        self.status = status


# --------------------------------------------------------------------------
# Catalog items: abstract base + concrete dataclasses
# --------------------------------------------------------------------------


@dataclass(kw_only=True)
class LibraryItem(ABC):
    """
    Abstract base for anything that can live in the catalog and be loaned out.

    kw_only=True is used so concrete subclasses can freely add their own
    required fields without fighting Python's "non-default argument follows
    default argument" dataclass ordering rule.
    """

    item_id: str
    title: str
    creator: str  # author, director, publisher, etc.
    status: ItemStatus = field(default=ItemStatus.AVAILABLE)

    @abstractmethod
    def loan_period_days(self) -> int:
        """How many days this type of item may be borrowed for."""
        raise NotImplementedError

    @abstractmethod
    def daily_late_fee(self) -> float:
        """Late fee charged per day, in dollars."""
        raise NotImplementedError

    def is_available(self) -> bool:
        return self.status is ItemStatus.AVAILABLE

    def describe(self) -> str:
        return f"[{self.item_id}] {self.title} — {self.creator} ({self.status.name})"


@dataclass(kw_only=True)
class Book(LibraryItem):
    isbn: str
    pages: int

    def loan_period_days(self) -> int:
        return 21

    def daily_late_fee(self) -> float:
        return 0.25


@dataclass(kw_only=True)
class DVD(LibraryItem):
    runtime_minutes: int

    def loan_period_days(self) -> int:
        return 7

    def daily_late_fee(self) -> float:
        return 1.00


@dataclass(kw_only=True)
class Magazine(LibraryItem):
    issue_number: int

    def loan_period_days(self) -> int:
        return 14

    def daily_late_fee(self) -> float:
        return 0.10


# --------------------------------------------------------------------------
# People & transactions
# --------------------------------------------------------------------------


@dataclass
class Member:
    member_id: str
    name: str
    email: str
    member_type: MemberType = MemberType.STANDARD
    borrowed_item_ids: list[str] = field(default_factory=list)
    max_concurrent_loans: int = 5

    def has_capacity(self) -> bool:
        return len(self.borrowed_item_ids) < self.max_concurrent_loans


@dataclass
class Loan:
    loan_id: str
    item_id: str
    member_id: str
    checkout_date: date
    due_date: date
    return_date: Optional[date] = None

    def is_returned(self) -> bool:
        return self.return_date is not None

    def days_late(self, as_of: Optional[date] = None) -> int:
        end = self.return_date if self.return_date is not None else (as_of or date.today())
        return max(0, (end - self.due_date).days)


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------


class Library:
    """Owns the catalog, membership roll, and active/past loans."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._catalog: dict[str, LibraryItem] = {}
        self._members: dict[str, Member] = {}
        self._loans: dict[str, Loan] = {}
        self._loan_counter: int = 0

    # -- registration ----------------------------------------------------

    def add_item(self, item: LibraryItem) -> None:
        self._catalog[item.item_id] = item

    def register_member(self, member: Member) -> None:
        self._members[member.member_id] = member

    # -- lookups -----------------------------------------------------------

    def get_item(self, item_id: str) -> LibraryItem:
        try:
            return self._catalog[item_id]
        except KeyError:
            raise ItemNotFoundError(item_id) from None

    def get_member(self, member_id: str) -> Member:
        try:
            return self._members[member_id]
        except KeyError:
            raise MemberNotFoundError(member_id) from None

    def available_items(self) -> list[LibraryItem]:
        return [item for item in self._catalog.values() if item.is_available()]

    # -- core workflows ------------------------------------------------------

    def checkout_item(
        self, item_id: str, member_id: str, checkout_date: Optional[date] = None
    ) -> Loan:
        item = self.get_item(item_id)
        member = self.get_member(member_id)

        if not item.is_available():
            raise ItemNotAvailableError(item_id, item.status)
        if not member.has_capacity():
            raise LibraryError(
                f"Member {member_id!r} has reached their loan limit "
                f"({member.max_concurrent_loans})"
            )

        today = checkout_date or date.today()
        due = today + timedelta(days=item.loan_period_days())

        self._loan_counter += 1
        loan = Loan(
            loan_id=f"L{self._loan_counter:05d}",
            item_id=item_id,
            member_id=member_id,
            checkout_date=today,
            due_date=due,
        )

        item.status = ItemStatus.CHECKED_OUT
        member.borrowed_item_ids.append(item_id)
        self._loans[loan.loan_id] = loan
        return loan

    def return_item(self, loan_id: str, return_date: Optional[date] = None) -> float:
        """Returns the item and reports the late fee owed (0.0 if on time)."""
        try:
            loan = self._loans[loan_id]
        except KeyError:
            raise LibraryError(f"No loan with id {loan_id!r}") from None

        item = self.get_item(loan.item_id)
        member = self.get_member(loan.member_id)

        loan.return_date = return_date or date.today()
        item.status = ItemStatus.AVAILABLE
        if loan.item_id in member.borrowed_item_ids:
            member.borrowed_item_ids.remove(loan.item_id)

        return loan.days_late() * item.daily_late_fee()

    def loans_for_member(self, member_id: str) -> list[Loan]:
        return [loan for loan in self._loans.values() if loan.member_id == member_id]


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------


def _demo() -> None:
    library = Library("Riverside Public Library")

    library.add_item(
        Book(item_id="B001", title="Dune", creator="Frank Herbert", isbn="9780441013593", pages=412)
    )
    library.add_item(
        DVD(item_id="D001", title="Arrival", creator="Denis Villeneuve", runtime_minutes=116)
    )
    library.add_item(
        Magazine(item_id="M001", title="National Geographic", creator="NG Society", issue_number=245)
    )

    library.register_member(Member(member_id="U001", name="Ada Lovelace", email="ada@example.com"))

    loan = library.checkout_item("B001", "U001")
    print(f"Checked out: {loan}")

    fee = library.return_item(loan.loan_id, return_date=loan.due_date + timedelta(days=3))
    print(f"Late fee owed: ${fee:.2f}")

    print("Available items:")
    for item in library.available_items():
        print(" ", item.describe())


if __name__ == "__main__":
    _demo()