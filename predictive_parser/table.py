"""Parse table construction for LL(1) and (experimentally) LL(k)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .sets import (
    END_MARK,
    EPSILON,
    compute_first,
    compute_first_k,
    compute_follow,
    compute_nullable,
    first_of_sequence,
)


class LL1Conflict(ValueError):
    """Raised when the grammar is not LL(1)."""

    def __init__(
        self,
        head: str,
        terminal: str,
        prod_a: list[str],
        prod_b: list[str],
    ) -> None:
        body_a = " ".join(prod_a) if prod_a != [EPSILON] else "\u03b5"
        body_b = " ".join(prod_b) if prod_b != [EPSILON] else "\u03b5"
        super().__init__(
            f"LL(1) conflict at ({head}, {terminal}): {body_a} vs {body_b}"
        )
        self.head = head
        self.terminal = terminal
        self.prod_a = prod_a
        self.prod_b = prod_b


def build_ll1_table(
    grammar: dict[str, list[list[str]]],
    start: str,
    terminals: Iterable[str],
    nullable: dict[str, bool] | None = None,
    first: dict[str, set[str]] | None = None,
    follow: dict[str, set[str]] | None = None,
) -> tuple[
    dict[tuple[str, str], list[str]],
    dict[str, bool],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    """Return ``(table, nullable, first, follow)`` for an LL(1) grammar."""

    term_set = set(terminals)
    if nullable is None:
        nullable = compute_nullable(grammar, term_set)
    if first is None:
        first = compute_first(grammar, term_set, nullable)
    if follow is None:
        follow = compute_follow(grammar, start, first, nullable)

    table: dict[tuple[str, str], list[str]] = {}
    for head, prods in grammar.items():
        for prod in prods:
            first_set = first_of_sequence(prod, first, nullable)
            for terminal in first_set - {EPSILON}:
                existing = table.get((head, terminal))
                if existing is not None and existing != prod:
                    raise LL1Conflict(head, terminal, existing, prod)
                table[head, terminal] = prod
            if EPSILON in first_set:
                for terminal in follow[head]:
                    existing = table.get((head, terminal))
                    if existing is not None and existing != prod:
                        raise LL1Conflict(head, terminal, existing, prod)
                    table[head, terminal] = prod
    return table, nullable, first, follow


def index_table(
    table: dict[tuple[str, str], list[str]],
) -> dict[str, dict[str, list[str]]]:
    """Pre-index the parse table by nonterminal for fast expected-set lookup."""

    index: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for (head, terminal), prod in table.items():
        index[head][terminal] = prod
    return dict(index)


# ---------------------------------------------------------------------------
# Experimental LL(k) prediction table
# ---------------------------------------------------------------------------


def build_llk_table(
    grammar: dict[str, list[list[str]]],
    start: str,
    terminals: Iterable[str],
    k: int,
) -> dict[tuple[str, tuple[str, ...]], list[str]]:
    """Build an LL(k) prediction table keyed by (nonterminal, terminal-tuple).

    For ``k == 1`` this is equivalent to :func:`build_ll1_table` modulo
    how FOLLOW sets are combined, but the LL(k) table is used by a
    different prediction path.  Conflicts raise :class:`LL1Conflict`.
    """

    if k < 1:
        raise ValueError("k must be >= 1")
    first_k = compute_first_k(grammar, set(terminals), k)
    # For simplicity we approximate LL(k) using FIRST_k(α) only.  This
    # covers most practical LL(k) grammars where FOLLOW disambiguation is
    # not required.
    table: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for head, prods in grammar.items():
        for prod in prods:
            for string in _first_k_of_prod(prod, first_k, k):
                key = (head, string)
                existing = table.get(key)
                if existing is not None and existing != prod:
                    raise LL1Conflict(head, " ".join(string), existing, prod)
                table[key] = prod
    return table


def _first_k_of_prod(
    prod: list[str],
    first_k: dict[str, set[tuple[str, ...]]],
    k: int,
) -> set[tuple[str, ...]]:
    result: set[tuple[str, ...]] = {()}
    for sym in prod:
        if sym == EPSILON:
            continue
        new_result: set[tuple[str, ...]] = set()
        for prefix in result:
            if len(prefix) >= k:
                new_result.add(prefix[:k])
                continue
            for suffix in first_k[sym]:
                new_result.add((prefix + suffix)[:k])
        result = new_result
    return result


__all__ = [
    "END_MARK",
    "LL1Conflict",
    "build_ll1_table",
    "build_llk_table",
    "index_table",
]
