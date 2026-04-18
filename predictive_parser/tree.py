"""Parse tree, visitor, and listener machinery."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .errors import SourceLocation
from .lexer import TokenLike, get_location


@dataclass
class ParseTree:
    """A concrete parse tree node.

    ``symbol`` is the head nonterminal or (for leaves) the terminal type.
    ``children`` is a list of child :class:`ParseTree` or token objects in
    left-to-right order.  ``production`` is the right-hand side that was
    used when deriving this node (``None`` for leaves).
    """

    symbol: str
    children: list[ParseTree | TokenLike] = field(default_factory=list)
    production: tuple[str, ...] | None = None
    location: SourceLocation = field(default_factory=SourceLocation)

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------

    def walk(self) -> Iterator[ParseTree | TokenLike]:
        """Yield every node and token in pre-order."""

        yield self
        for child in self.children:
            if isinstance(child, ParseTree):
                yield from child.walk()
            else:
                yield child

    def terminals(self) -> Iterator[TokenLike]:
        """Yield only the terminal tokens in left-to-right order."""

        for child in self.children:
            if isinstance(child, ParseTree):
                yield from child.terminals()
            else:
                yield child

    def pretty(self, indent: int = 0) -> str:
        """Return a human-readable indented dump of the tree."""

        pad = "  " * indent
        lines = [f"{pad}{self.symbol}"]
        for child in self.children:
            if isinstance(child, ParseTree):
                lines.append(child.pretty(indent + 1))
            else:
                val = getattr(child, "value", None)
                ttype = getattr(child, "type", str(child))
                if val is not None and val != ttype:
                    lines.append(f"  {pad}{ttype}({val!r})")
                else:
                    lines.append(f"  {pad}{ttype}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"ParseTree({self.symbol!r}, children={len(self.children)})"


# ---------------------------------------------------------------------------
# Visitor / listener
# ---------------------------------------------------------------------------


class ParseTreeVisitor:
    """Generic visitor.

    Override ``visit_<symbol>`` to handle a specific nonterminal; otherwise
    the default implementation visits every child and returns a list of
    results.
    """

    def visit(self, node: ParseTree | TokenLike) -> Any:
        if not isinstance(node, ParseTree):
            return self.visit_terminal(node)
        method = getattr(self, f"visit_{_safe_name(node.symbol)}", None)
        if method is not None:
            return method(node)
        return self.visit_children(node)

    def visit_children(self, node: ParseTree) -> list[Any]:
        return [self.visit(c) for c in node.children]

    def visit_terminal(self, token: TokenLike) -> Any:
        """Default terminal handler — returns the token unchanged."""

        return token


class ParseTreeListener:
    """Enter/exit callbacks called while walking a tree.

    Override ``enter_<symbol>`` / ``exit_<symbol>`` for per-node hooks.
    """

    def walk(self, node: ParseTree | TokenLike) -> None:
        if not isinstance(node, ParseTree):
            self.visit_terminal(node)
            return
        self.enter_every_rule(node)
        entry = getattr(self, f"enter_{_safe_name(node.symbol)}", None)
        if entry is not None:
            entry(node)
        for child in node.children:
            self.walk(child)
        exitter = getattr(self, f"exit_{_safe_name(node.symbol)}", None)
        if exitter is not None:
            exitter(node)
        self.exit_every_rule(node)

    def enter_every_rule(self, node: ParseTree) -> None:
        """Called on every nonterminal before descending."""

    def exit_every_rule(self, node: ParseTree) -> None:
        """Called on every nonterminal after its children are walked."""

    def visit_terminal(self, token: TokenLike) -> None:
        """Called for every terminal token encountered."""


def walk_tree(listener: ParseTreeListener, node: ParseTree | TokenLike) -> None:
    """Functional wrapper for :meth:`ParseTreeListener.walk`."""

    listener.walk(node)


def _safe_name(symbol: str) -> str:
    """Convert a symbol into a valid Python identifier.

    Allows grammar symbols like ``if`` or ``Expr'`` (prime) to still have
    visitor dispatch methods like ``visit_if`` / ``visit_Expr_p``.
    """

    out: list[str] = []
    for ch in symbol:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append(f"_{ord(ch):x}")
    if not out or out[0].isdigit():
        out.insert(0, "s_")
    return "".join(out)


def tree_location(children: list[ParseTree | TokenLike]) -> SourceLocation:
    """Derive a :class:`SourceLocation` from the first concrete child."""

    for child in children:
        if isinstance(child, ParseTree):
            if child.location.line is not None or child.location.offset is not None:
                return child.location
        else:
            loc = get_location(child)
            if loc.line is not None or loc.offset is not None:
                return loc
    return SourceLocation()


__all__ = [
    "ParseTree",
    "ParseTreeListener",
    "ParseTreeVisitor",
    "tree_location",
    "walk_tree",
]
