"""Cypher exception types."""

from __future__ import annotations

from collections.abc import Iterable


class CypherError(Exception):
    """Base class for Cypher errors."""


class DiscoveryError(CypherError):
    """Raised when archetype discovery or cache loading fails."""


class CyclusInvocationError(DiscoveryError):
    """Raised when the selected Cyclus executable cannot be invoked."""


class ValidationError(CypherError):
    """Raised when one or more simulation validation checks fail."""

    def __init__(self, problems: str | Iterable[str]) -> None:
        if isinstance(problems, str):
            self.problems = (problems,)
        else:
            self.problems = tuple(problems)
        message = "Cypher validation failed:"
        if self.problems:
            message += "\n" + "\n".join(f"- {problem}" for problem in self.problems)
        super().__init__(message)
