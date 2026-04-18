"""Semantic-action types used by :class:`PredictiveParser`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Action = Callable[[list[Any]], Any]
"""Callable that receives children values and returns a semantic value."""


def default_action(values: list[Any]) -> Any:
    """Default semantic action — return the first child's value (Bison-style).

    Falls back to ``None`` for empty productions.
    """

    return values[0] if values else None


def concat_action(values: list[Any]) -> Any:
    """Helper action that concatenates children into a tuple."""

    return tuple(values)


@dataclass
class ProductionSpec:
    """A production with an attached (optional) semantic action.

    ``head`` is the nonterminal on the left-hand side.
    ``body`` is the right-hand side as a tuple of symbols.  The empty tuple
    represents an ε-production.
    ``action`` is ``None`` to keep the default behavior.
    """

    head: str
    body: tuple[str, ...]
    action: Action | None = None
    source_line: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def key(self) -> tuple[str, tuple[str, ...]]:
        return self.head, self.body


__all__ = [
    "Action",
    "ProductionSpec",
    "concat_action",
    "default_action",
]
