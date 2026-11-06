"""allowed_access_levels is the single source of truth for who sees what
(AGENTS.md §5.7). These are plain Python objects — no database needed."""

import uuid

import pytest

from app.models import AccessLevel, User, UserRole
from app.security import allowed_access_levels


def _make_user(role: UserRole) -> User:
    return User(id=uuid.uuid4(), email="demo@test.local", name="Demo", role=role)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (UserRole.EMPLOYEE, [AccessLevel.ALL]),
        (UserRole.MANAGER, [AccessLevel.ALL, AccessLevel.MANAGERS]),
        (UserRole.ADMIN, [AccessLevel.ALL, AccessLevel.MANAGERS]),
    ],
)
def test_allowed_access_levels_by_role(role: UserRole, expected: list[AccessLevel]) -> None:
    user = _make_user(role)

    assert allowed_access_levels(user) == expected


def test_employee_never_sees_managers_level() -> None:
    user = _make_user(UserRole.EMPLOYEE)

    assert AccessLevel.MANAGERS not in allowed_access_levels(user)
