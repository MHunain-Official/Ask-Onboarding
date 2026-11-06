"""Security tests need the same real-Postgres fixtures as the integration
suite — the DB session (reset before each test), demo/manager/admin
users, the `TestClient` factory, and the circuit-breaker/rate-limiter
resets — so they are reused here rather than duplicated.
"""

from tests.integration.conftest import (  # noqa: F401
    _reset_circuit_breaker,
    _reset_rate_limiter,
    admin_user,
    db,
    demo_user,
    make_client,
    manager_user,
)
