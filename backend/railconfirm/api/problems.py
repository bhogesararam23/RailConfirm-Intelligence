"""API-level problems that are not domain failures.

Domain errors explain why a *prediction* is impossible. This explains why an endpoint
cannot help at all — an unknown report id, or a server configured to keep no history —
and carries the status and code so the documented error envelope stays the only shape
clients have to parse.
"""

from __future__ import annotations


class ApiProblem(Exception):
    """A request that cannot be answered, with the status it should be answered with."""

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
