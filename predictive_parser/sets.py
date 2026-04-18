"""FIRST / FOLLOW / NULLABLE computation for LL(1) and LL(k)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

EPSILON = ""
END_MARK = "$"


# ---------------------------------------------------------------------------
# LL(1) sets
# ---------------------------------------------------------------------------


def compute_nullable(
    grammar: dict[str, list[list[str]]],
    terminals: Iterable[str],
) -> dict[str, bool]:
    """Return a map from symbol -> whether it can derive ε."""

    nullable: dict[str, bool] = {EPSILON: True}
    for terminal in terminals:
        nullable[terminal] = False
    for head, prods in grammar.items():
        nullable[head] = any(prod == [EPSILON] for prod in prods) or nullable.get(
            head, False
        )

    changed = True
    while changed:
        changed = False
        for head, prods in grammar.items():
            if nullable[head]:
                continue
            for prod in prods:
                if all(nullable.get(s, False) for s in prod):
                    nullable[head] = True
                    changed = True
                    break
    return nullable


def compute_first(
    grammar: dict[str, list[list[str]]],
    terminals: Iterable[str],
    nullable: dict[str, bool],
) -> dict[str, set[str]]:
    """Return a map from symbol -> FIRST set (including ε when applicable)."""

    first: dict[str, set[str]] = {t: {t} for t in terminals}
    for head in grammar:
        first[head] = set()

    changed = True
    while changed:
        changed = False
        for head, prods in grammar.items():
            before = len(first[head])
            for prod in prods:
                nullable_prefix = True
                for sym in prod:
                    if sym == EPSILON:
                        first[head].add(EPSILON)
                        break
                    first[head] |= first[sym] - {EPSILON}
                    if not nullable.get(sym, False):
                        nullable_prefix = False
                        break
                if nullable_prefix and all(
                    nullable.get(s, False) or s == EPSILON for s in prod
                ):
                    first[head].add(EPSILON)
            if len(first[head]) > before:
                changed = True
    return first


def first_of_sequence(
    symbols: Sequence[str],
    first: dict[str, set[str]],
    nullable: dict[str, bool],
) -> set[str]:
    """Return FIRST(α) for a sequence of grammar symbols α."""

    result: set[str] = set()
    for sym in symbols:
        if sym == EPSILON:
            result.add(EPSILON)
            return result
        result |= first[sym] - {EPSILON}
        if not nullable.get(sym, False):
            return result
    result.add(EPSILON)
    return result


def compute_follow(
    grammar: dict[str, list[list[str]]],
    start: str,
    first: dict[str, set[str]],
    nullable: dict[str, bool],
) -> dict[str, set[str]]:
    """Return a map from nonterminal -> FOLLOW set."""

    follow: dict[str, set[str]] = {
        head: ({END_MARK} if head == start else set()) for head in grammar
    }
    nonterminals = set(grammar.keys())

    changed = True
    while changed:
        changed = False
        for head, prods in grammar.items():
            for prod in prods:
                trailer = follow[head].copy()
                for sym in reversed(prod):
                    if sym in nonterminals:
                        before = len(follow[sym])
                        follow[sym] |= trailer
                        if len(follow[sym]) > before:
                            changed = True
                        if nullable.get(sym, False):
                            trailer = trailer | (first[sym] - {EPSILON})
                        else:
                            trailer = first[sym] - {EPSILON}
                    elif sym == EPSILON:
                        continue
                    else:
                        trailer = {sym}
    return follow


# ---------------------------------------------------------------------------
# LL(k) — FIRST_k / FOLLOW_k (length-bounded strings of terminals)
# ---------------------------------------------------------------------------


def _concat_k(
    a: set[tuple[str, ...]], b: set[tuple[str, ...]], k: int
) -> set[tuple[str, ...]]:
    """k-length truncated concatenation: {(x++y)[:k] | x in a, y in b}."""

    out: set[tuple[str, ...]] = set()
    for x in a:
        if len(x) >= k:
            out.add(x[:k])
            continue
        for y in b:
            out.add((x + y)[:k])
    return out


def compute_first_k(
    grammar: dict[str, list[list[str]]],
    terminals: Iterable[str],
    k: int,
) -> dict[str, set[tuple[str, ...]]]:
    """Return FIRST_k sets: strings of terminals of length ≤ k.

    The empty string ``()`` represents ε.
    """

    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    first: dict[str, set[tuple[str, ...]]] = {t: {(t,)} for t in terminals}
    for head in grammar:
        first[head] = set()

    def first_of_seq(seq: Sequence[str]) -> set[tuple[str, ...]]:
        result: set[tuple[str, ...]] = {()}
        for sym in seq:
            if sym == EPSILON:
                continue
            result = _concat_k(result, first[sym], k)
        return result

    changed = True
    while changed:
        changed = False
        for head, prods in grammar.items():
            before = len(first[head])
            for prod in prods:
                if prod == [EPSILON]:
                    first[head].add(())
                else:
                    first[head] |= first_of_seq(prod)
            if len(first[head]) > before:
                changed = True
    return first


__all__ = [
    "END_MARK",
    "EPSILON",
    "compute_first",
    "compute_first_k",
    "compute_follow",
    "compute_nullable",
    "first_of_sequence",
]
