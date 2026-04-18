#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""
  A simple (naive) LL(1) parser.
  Copyright (C) 2016 Victor C. Martins (dxhj)

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence, Union, runtime_checkable

EPSILON = ""


@runtime_checkable
class TokenLike(Protocol):
    @property
    def type(self) -> str: ...


@dataclass(frozen=True)
class SimpleToken:
    type: str
    value: str | None = None


TokenInput = Sequence[Union[str, TokenLike]]


def _normalize_tokens(seq: TokenInput) -> list[TokenLike]:
    """Normalize mixed input (strings and/or TokenLike) into a token list.

    Strings are wrapped in :class:`SimpleToken`. Existing token-like objects
    are passed through unchanged so caller metadata (line, column, value) is
    preserved for downstream use.
    """
    result: list[TokenLike] = []
    for item in seq:
        if isinstance(item, str):
            result.append(SimpleToken(type=item, value=item))
        else:
            result.append(item)
    return result


@dataclass
class MatchResult:
    """Outcome of a parse attempt with optional diagnostic information."""

    success: bool
    position: int = 0
    expected: frozenset[str] = field(default_factory=frozenset)
    got: str | None = None

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self) -> str:
        if self.success:
            return "MatchResult(success=True)"
        return (
            f"MatchResult(success=False, position={self.position}, "
            f"expected={set(self.expected)}, got={self.got!r})"
        )


class PredictiveParser:
    def __init__(self, start: str, grammar: dict[str, list[list[str]]]) -> None:
        self.start = start
        self.grammar = grammar
        self.terminals, self.nonterminals = self._classify_symbols()
        self._validate_grammar()
        self.null_dict = self._gen_nullable()
        self.first_dict = self._gen_first()
        self.follow_dict = self._gen_follow()
        self.table = self._gen_table()

    def __repr__(self) -> str:
        return (
            f"PredictiveParser(start={self.start!r}, "
            f"nonterminals={len(self.nonterminals)}, "
            f"terminals={len(self.terminals)})"
        )

    def _classify_symbols(self) -> tuple[set[str], set[str]]:
        """Derive terminal and nonterminal sets from the grammar structure.

        Nonterminals are exactly the keys of the grammar dict.  Every other
        non-epsilon symbol that appears in a production body is a terminal.
        """
        nonterminals = set(self.grammar.keys())
        terminals: set[str] = set()
        for prods in self.grammar.values():
            for prod in prods:
                for sym in prod:
                    if sym != EPSILON and sym not in nonterminals:
                        terminals.add(sym)
        return terminals, nonterminals

    def is_terminal(self, sym: str) -> bool:
        return sym in self.terminals

    def is_nonterminal(self, sym: str) -> bool:
        return sym in self.nonterminals

    def _validate_grammar(self) -> None:
        if self.start not in self.grammar:
            raise ValueError(
                f"start symbol {self.start!r} is not defined in the grammar"
            )
        for head, prods in self.grammar.items():
            for prod in prods:
                for sym in prod:
                    if sym != EPSILON and sym[0].isupper() and sym not in self.grammar:
                        raise ValueError(
                            f"nonterminal {sym!r} in production "
                            f"{head} \u2192 {' '.join(prod)} has no "
                            f"defining rule in the grammar"
                        )

    def _run_match(
        self,
        seq: TokenInput,
        verbose: bool = False,
        display_stack: bool = False,
    ) -> MatchResult:
        tokens = _normalize_tokens(seq)
        tokens.append(SimpleToken(type="$", value="$"))
        si = 0
        stack = ["$", self.start]
        top = self.start
        while top != "$":
            cur_type = tokens[si].type
            if display_stack and verbose:
                print("Stack:", stack)
            if top == cur_type:
                si += 1
                if verbose:
                    print(f"** Action: match `{top}`")
                stack.pop()
            elif self.is_terminal(top):
                return MatchResult(
                    success=False,
                    position=si,
                    expected=frozenset({top}),
                    got=cur_type,
                )
            else:
                prod = self.table.get((top, cur_type))
                if prod is None:
                    expected = frozenset(
                        t for nt, t in self.table if nt == top
                    )
                    if verbose:
                        print(
                            f"ERROR: Not able to find derivation of"
                            f" {top} on `{cur_type}`"
                        )
                    return MatchResult(
                        success=False,
                        position=si,
                        expected=expected,
                        got=cur_type,
                    )
                stack.pop()
                if prod == [EPSILON]:
                    if verbose:
                        print(
                            f"** Action: derive {top} on "
                            f"`{cur_type}` to: \u03b5"
                        )
                else:
                    if verbose:
                        print(
                            f"** Action: derive {top} on "
                            f"`{cur_type}` to: {' '.join(prod)}"
                        )
                    stack.extend(reversed(prod))
            top = stack[-1]
        if tokens[si].type == "$":
            return MatchResult(success=True, position=si)
        return MatchResult(
            success=False,
            position=si,
            expected=frozenset({"$"}),
            got=tokens[si].type,
        )

    def match(self, seq: TokenInput) -> bool:
        return self._run_match(seq).success

    def detailed_match(self, seq: TokenInput) -> MatchResult:
        """Like match(), but returns a MatchResult with diagnostic info."""
        return self._run_match(seq)

    def verbose_match(
        self, seq: TokenInput, display_stack: bool = False
    ) -> bool:
        return self._run_match(
            seq, verbose=True, display_stack=display_stack
        ).success

    def _gen_table(self) -> dict[tuple[str, str], list[str]]:
        table: dict[tuple[str, str], list[str]] = {}
        for head, prods in self.grammar.items():
            for prod in prods:
                first_set = self.first(prod)
                for terminal in first_set - {EPSILON}:
                    if (head, terminal) in table and table[head, terminal] != prod:
                        raise ValueError(
                            f"LL(1) conflict at ({head}, {terminal}): "
                            f"{table[head, terminal]} vs {prod}"
                        )
                    table[head, terminal] = prod
                if EPSILON in first_set:
                    for terminal in self.follow_dict[head]:
                        if (head, terminal) in table and table[head, terminal] != prod:
                            raise ValueError(
                                f"LL(1) conflict at ({head}, {terminal}): "
                                f"{table[head, terminal]} vs {prod}"
                            )
                        table[head, terminal] = prod
        return table

    def print_table(self) -> None:
        for nonterminal in self.nonterminals:
            for terminal in self.terminals | {"$"}:
                prod = self.table.get((nonterminal, terminal))
                if prod is not None:
                    print(f"({nonterminal}, {terminal}) = {prod}")

    def _gen_nullable(self) -> dict[str, bool]:
        null_dict: dict[str, bool] = {EPSILON: True}
        for terminal in self.terminals:
            null_dict[terminal] = False
        for head, prods in self.grammar.items():
            null_dict[head] = False
            for prod in prods:
                for sym in prod:
                    if sym == EPSILON:
                        null_dict[head] = True

        changed = True
        while changed:
            changed = False
            for head, prods in self.grammar.items():
                if not null_dict[head]:
                    for prod in prods:
                        if all(null_dict[s] for s in prod):
                            null_dict[head] = True
                            changed = True
        return null_dict

    def nullable(self, symbols: list[str]) -> bool:
        return all(self.null_dict[s] for s in symbols)

    def _gen_first(self) -> dict[str, set[str]]:
        first_dict: dict[str, set[str]] = {}
        for terminal in self.terminals:
            first_dict[terminal] = {terminal}
        for head in self.grammar:
            first_dict[head] = set()

        changed = True
        while changed:
            changed = False
            for head, prods in self.grammar.items():
                before = len(first_dict[head])
                for prod in prods:
                    for i, sym in enumerate(prod):
                        if not self.nullable(prod[:i]):
                            break
                        if sym == EPSILON:
                            first_dict[head].add(EPSILON)
                        else:
                            first_dict[head] |= first_dict[sym] - {EPSILON}
                    if self.nullable(prod):
                        first_dict[head].add(EPSILON)
                if len(first_dict[head]) > before:
                    changed = True
        return first_dict

    def first(self, symbols: list[str]) -> set[str]:
        result: set[str] = set()
        for sym in symbols:
            if sym == EPSILON:
                result.add(EPSILON)
                return result
            result |= self.first_dict[sym] - {EPSILON}
            if not self.null_dict[sym]:
                return result
        result.add(EPSILON)
        return result

    def _gen_follow(self) -> dict[str, set[str]]:
        follow_dict: dict[str, set[str]] = {}
        for head in self.grammar:
            follow_dict[head] = {"$"} if head == self.start else set()

        changed = True
        while changed:
            changed = False
            for head, prods in self.grammar.items():
                for prod in prods:
                    for i in range(len(prod) - 1):
                        if self.is_nonterminal(prod[i]):
                            before = len(follow_dict[prod[i]])
                            follow_dict[prod[i]] |= (
                                self.first(prod[i + 1 :]) - {EPSILON}
                            )
                            if len(follow_dict[prod[i]]) > before:
                                changed = True

                    for i in reversed(range(len(prod))):
                        if self.is_nonterminal(prod[i]) and self.nullable(
                            prod[i + 1 :]
                        ):
                            before = len(follow_dict[prod[i]])
                            follow_dict[prod[i]] |= follow_dict[head]
                            if len(follow_dict[prod[i]]) > before:
                                changed = True
        return follow_dict
