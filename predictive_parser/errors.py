"""Error types, source locations, and error-listener protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .lexer import TokenLike


@dataclass(frozen=True)
class SourceLocation:
    """Position in the source text.

    ``line`` and ``column`` are 1-indexed.  ``offset`` is a 0-indexed byte/char
    offset.  Any field may be ``None`` when the underlying lexer does not
    provide it.
    """

    line: int | None = None
    column: int | None = None
    offset: int | None = None

    def __str__(self) -> str:
        if self.line is not None and self.column is not None:
            return f"line {self.line}, column {self.column}"
        if self.offset is not None:
            return f"offset {self.offset}"
        return "<unknown>"


@dataclass
class ParseError(Exception):
    """Raised (or reported) when the parser encounters a syntax error."""

    message: str
    location: SourceLocation = field(default_factory=SourceLocation)
    expected: frozenset[str] = field(default_factory=frozenset)
    got: str | None = None
    position: int = 0

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@dataclass
class LexerError(Exception):
    """Raised when the lexer cannot tokenize the input."""

    message: str
    location: SourceLocation = field(default_factory=SourceLocation)

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@dataclass
class ActionError(Exception):
    """Wraps an exception raised inside a semantic action.

    Carries the production that was firing and the source location so users
    get a meaningful traceback instead of an opaque parser-internal failure.
    """

    production: tuple[str, tuple[str, ...]]
    original: BaseException
    location: SourceLocation = field(default_factory=SourceLocation)

    def __post_init__(self) -> None:
        head, body = self.production
        rhs = " ".join(body) if body else "\u03b5"
        msg = (
            f"error in semantic action for {head} -> {rhs} "
            f"at {self.location}: {type(self.original).__name__}: {self.original}"
        )
        super().__init__(msg)
        self.message = msg


class ErrorListener:
    """Callback interface for parser errors.

    Subclass and pass to :class:`PredictiveParser` to customize reporting.
    """

    def syntax_error(
        self,
        location: SourceLocation,
        expected: frozenset[str],
        got: TokenLike | None,
        message: str,
    ) -> None:  # pragma: no cover - interface method
        raise NotImplementedError


class DefaultErrorListener(ErrorListener):
    """Collects errors into a list so multiple can be reported per parse."""

    def __init__(self) -> None:
        self.errors: list[ParseError] = []

    def syntax_error(
        self,
        location: SourceLocation,
        expected: frozenset[str],
        got: TokenLike | None,
        message: str,
    ) -> None:
        got_type = getattr(got, "type", None) if got is not None else None
        self.errors.append(
            ParseError(
                message=message,
                location=location,
                expected=expected,
                got=got_type,
            )
        )


class RaisingErrorListener(ErrorListener):
    """Raises :class:`ParseError` on the first syntax error."""

    def syntax_error(
        self,
        location: SourceLocation,
        expected: frozenset[str],
        got: TokenLike | None,
        message: str,
    ) -> None:
        got_type = getattr(got, "type", None) if got is not None else None
        raise ParseError(
            message=message,
            location=location,
            expected=expected,
            got=got_type,
        )


__all__ = [
    "ActionError",
    "DefaultErrorListener",
    "ErrorListener",
    "LexerError",
    "ParseError",
    "RaisingErrorListener",
    "SourceLocation",
]
