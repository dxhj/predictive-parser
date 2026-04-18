"""Token types and a small regex-based :class:`Lexer`.

The parser is lexer-agnostic: it only requires objects that expose a
``.type`` attribute (the :class:`TokenLike` protocol).  Users may freely mix
:class:`SimpleToken`, tokens from PLY, or their own dataclasses.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .errors import LexerError, SourceLocation


@runtime_checkable
class TokenLike(Protocol):
    """Minimal token protocol: only ``.type`` is required for parsing."""

    @property
    def type(self) -> str: ...


@dataclass(frozen=True)
class SimpleToken:
    """Lightweight token with optional value and source location."""

    type: str
    value: str | None = None
    line: int | None = None
    column: int | None = None
    offset: int | None = None

    @property
    def location(self) -> SourceLocation:
        return SourceLocation(line=self.line, column=self.column, offset=self.offset)


@dataclass(frozen=True)
class Token:
    """Full token with source location metadata.

    Backward-compatible superset of :class:`SimpleToken`.
    """

    type: str
    value: str
    line: int = 1
    column: int = 1
    offset: int = 0

    @property
    def location(self) -> SourceLocation:
        return SourceLocation(line=self.line, column=self.column, offset=self.offset)


TokenInput = Sequence[str | TokenLike]
"""An eager sequence of tokens (strings or token-like objects)."""

TokenStream = Iterable[str | TokenLike] | Iterator[str | TokenLike]
"""Any iterable yielding tokens — lists, generators, lexer output."""


def normalize_tokens(seq: TokenStream) -> Iterator[TokenLike]:
    """Yield :class:`TokenLike` values from any iterable of str/token inputs.

    Strings are wrapped in :class:`SimpleToken` preserving the text as the
    ``.value``.  Token-like objects pass through unchanged.
    """

    for item in seq:
        if isinstance(item, str):
            yield SimpleToken(type=item, value=item)
        else:
            yield item


def get_location(tok: TokenLike | None) -> SourceLocation:
    """Extract a :class:`SourceLocation` from any token-like object."""

    if tok is None:
        return SourceLocation()
    line = getattr(tok, "line", None)
    if line is None:
        line = getattr(tok, "lineno", None)
    column = getattr(tok, "column", None)
    offset = getattr(tok, "offset", None)
    if offset is None:
        offset = getattr(tok, "lexpos", None)
    return SourceLocation(line=line, column=column, offset=offset)


# ---------------------------------------------------------------------------
# Regex-based lexer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenRule:
    """A single lexer rule.

    Attributes:
        name: Token type name used by the parser (e.g. ``"id"``).
        pattern: Regular expression matched against the input.
        skip: If True, matched text is consumed but no token is emitted
            (e.g. whitespace, comments).
        keywords: Optional mapping from matched text to a specialized token
            type, useful for keyword/identifier disambiguation.
    """

    name: str
    pattern: str
    skip: bool = False
    keywords: dict[str, str] | None = None


class Lexer:
    """A compact regex-based lexer producing :class:`Token` objects.

    Rules are matched in order — the first rule whose regex matches at the
    current position wins.  This mirrors the behavior of PLY and flex.
    """

    def __init__(self, rules: Sequence[TokenRule]) -> None:
        if not rules:
            raise ValueError("Lexer needs at least one rule")
        self.rules: tuple[TokenRule, ...] = tuple(rules)
        self._compiled: list[tuple[TokenRule, re.Pattern[str]]] = [
            (r, re.compile(r.pattern)) for r in self.rules
        ]

    def tokenize(self, text: str) -> list[Token]:
        """Fully tokenize ``text`` into a list."""

        return list(self.lex(text))

    def lex(self, text: str) -> Iterator[Token]:
        """Yield tokens from ``text`` lazily."""

        pos = 0
        line = 1
        col = 1
        n = len(text)
        while pos < n:
            best: tuple[TokenRule, re.Match[str]] | None = None
            for rule, regex in self._compiled:
                m = regex.match(text, pos)
                if m is not None and m.end() > m.start():
                    best = (rule, m)
                    break
            if best is None:
                raise LexerError(
                    f"unexpected character {text[pos]!r}",
                    SourceLocation(line=line, column=col, offset=pos),
                )
            rule, m = best
            matched = m.group(0)
            if not rule.skip:
                ttype = rule.name
                if rule.keywords and matched in rule.keywords:
                    ttype = rule.keywords[matched]
                yield Token(
                    type=ttype,
                    value=matched,
                    line=line,
                    column=col,
                    offset=pos,
                )
            # Advance line/column tracking.
            for ch in matched:
                if ch == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
            pos = m.end()


def from_ply_lexer(lexer: Any) -> Iterator[TokenLike]:
    """Adapter that pulls tokens from a PLY-style ``lexer.token()`` source.

    ``lexer.token()`` returns the next token or ``None`` when input is
    exhausted.  This lets you plug ``lex.lex()`` directly into
    ``parser.parse(from_ply_lexer(mylex))`` with no shim code on the user's
    side.
    """

    while True:
        tok = lexer.token()
        if tok is None:
            return
        yield tok


__all__ = [
    "Lexer",
    "SimpleToken",
    "Token",
    "TokenInput",
    "TokenLike",
    "TokenRule",
    "TokenStream",
    "from_ply_lexer",
    "get_location",
    "normalize_tokens",
]
