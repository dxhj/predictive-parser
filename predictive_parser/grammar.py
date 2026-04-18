"""Grammar data class and a small BNF/EBNF DSL loader.

Grammar DSL example::

    %start Expr

    Expr   -> Term Exprp ;
    Exprp  -> '+' Term Exprp | epsilon ;
    Term   -> Factor Termp ;
    Termp  -> '*' Factor Termp | epsilon ;
    Factor -> '(' Expr ')' | 'id' ;

EBNF sugar (``?``, ``*``, ``+``, ``(...)``) is automatically desugared into
fresh nonterminals; see :mod:`predictive_parser.transforms`.

Inline semantic actions (Bison-style)::

    Expr -> Term '+' Expr   { $$ = $1 + $3 } ;

``$1..$N`` refer to the children values (1-indexed), ``$$`` is the
production's return value.

Comments: ``//...`` to end of line, ``#...`` to end of line, or
``/* ... */`` block.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .actions import Action, ProductionSpec
from .errors import ParseError, SourceLocation
from .sets import EPSILON


@dataclass
class Grammar:
    """An immutable grammar representation keyed by head nonterminal.

    ``productions`` preserves rule order per head (important for
    deterministic LL(1) conflict error messages).
    """

    start: str
    productions: dict[str, list[ProductionSpec]]

    @classmethod
    def from_rules(
        cls,
        start: str,
        rules: dict[str, list[list[str]]],
        actions: dict[tuple[str, tuple[str, ...]], Action] | None = None,
    ) -> Grammar:
        """Build a :class:`Grammar` from a plain-dict specification.

        Epsilon productions are normalized to an empty tuple ``()`` regardless
        of whether the input used ``[""]`` or ``[]``.
        """

        acts = actions or {}
        productions: dict[str, list[ProductionSpec]] = {}
        for head, prods in rules.items():
            productions[head] = []
            for prod in prods:
                if prod == [EPSILON] or prod == []:
                    body: tuple[str, ...] = ()
                else:
                    body = tuple(prod)
                action = acts.get((head, body))
                productions[head].append(
                    ProductionSpec(head=head, body=body, action=action)
                )
        return cls(start=start, productions=productions)

    # ------------------------------------------------------------------
    # Convenience views
    # ------------------------------------------------------------------

    def as_dict(self) -> dict[str, list[list[str]]]:
        """Return a plain dict view suitable for the low-level API."""

        return {
            head: [list(p.body) if p.body else [EPSILON] for p in prods]
            for head, prods in self.productions.items()
        }

    def iter_productions(self) -> Iterable[ProductionSpec]:
        for prods in self.productions.values():
            yield from prods

    def get_action(self, head: str, body: tuple[str, ...]) -> Action | None:
        for p in self.productions.get(head, ()):
            if p.body == body:
                return p.action
        return None

    def set_action(
        self, head: str, body: tuple[str, ...], action: Action
    ) -> None:
        for p in self.productions.get(head, ()):
            if p.body == body:
                p.action = action
                return
        raise KeyError(f"production {head} -> {' '.join(body) or 'ε'!r} not found")


# ---------------------------------------------------------------------------
# DSL parser
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(
    r"""
    (?P<WS>        \s+)
  | (?P<LCOMMENT>  //[^\n]*|\#[^\n]*)
  | (?P<BCOMMENT>  /\*[\s\S]*?\*/)
  | (?P<ARROW>     ->|::=|:)
  | (?P<PIPE>      \|)
  | (?P<SEMI>      ;)
  | (?P<LPAREN>    \()
  | (?P<RPAREN>    \))
  | (?P<STAR>      \*)
  | (?P<PLUS>      \+)
  | (?P<QMARK>     \?)
  | (?P<EQ>        =)
  | (?P<STRING>    '(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
  | (?P<DIRECTIVE> %[A-Za-z_][A-Za-z_0-9]*)
  | (?P<IDENT>     [A-Za-z_\u0080-\U0010FFFF][A-Za-z_0-9'\u0080-\U0010FFFF]*)
    """,
    re.VERBOSE,
)


@dataclass
class _Tok:
    kind: str
    value: str
    line: int
    col: int


def _tokenize_dsl(src: str) -> list[_Tok]:
    toks: list[_Tok] = []
    pos = 0
    line = 1
    col = 1
    n = len(src)
    while pos < n:
        ch = src[pos]
        # Action block: consume raw text up to matching '}'.
        if ch == "{":
            depth = 1
            start_line, start_col = line, col
            pos += 1
            col += 1
            buf: list[str] = []
            while pos < n and depth > 0:
                c = src[pos]
                if c == "{":
                    depth += 1
                    buf.append(c)
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        pos += 1
                        col += 1
                        break
                    buf.append(c)
                else:
                    buf.append(c)
                if c == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                pos += 1
            else:
                if depth > 0:
                    raise ParseError(
                        "unterminated action block",
                        SourceLocation(line=start_line, column=start_col),
                    )
            toks.append(
                _Tok(kind="ACTION", value="".join(buf), line=start_line, col=start_col)
            )
            continue
        m = _TOKEN_RE.match(src, pos)
        if m is None:
            raise ParseError(
                f"unexpected character {src[pos]!r} in grammar",
                SourceLocation(line=line, column=col, offset=pos),
            )
        kind = m.lastgroup
        assert kind is not None
        val = m.group(0)
        if kind not in ("WS", "LCOMMENT", "BCOMMENT"):
            toks.append(_Tok(kind=kind, value=val, line=line, col=col))
        for c in val:
            if c == "\n":
                line += 1
                col = 1
            else:
                col += 1
        pos = m.end()
    return toks


@dataclass
class _EBNFNode:
    """AST for a parsed DSL rule body alternative before desugaring."""

    kind: str
    value: Any = None
    children: list[_EBNFNode] = field(default_factory=list)


class _DSLParser:
    def __init__(self, toks: list[_Tok]) -> None:
        self.toks = toks
        self.pos = 0
        self.start: str | None = None
        self.productions: list[tuple[str, list[_EBNFNode], str | None]] = []
        self.token_rules: list[tuple[str, str]] = []
        self.skip_rules: list[tuple[str, str]] = []

    # --- low-level helpers ---------------------------------------------

    def _peek(self, offset: int = 0) -> _Tok | None:
        idx = self.pos + offset
        return self.toks[idx] if idx < len(self.toks) else None

    def _eat(self, kind: str) -> _Tok:
        t = self._peek()
        if t is None or t.kind != kind:
            got = f"{t.kind} {t.value!r}" if t else "end of input"
            loc = SourceLocation(
                line=(t.line if t else None),
                column=(t.col if t else None),
            )
            raise ParseError(f"expected {kind}, got {got}", loc)
        self.pos += 1
        return t

    def _accept(self, kind: str) -> _Tok | None:
        t = self._peek()
        if t is not None and t.kind == kind:
            self.pos += 1
            return t
        return None

    # --- top-level -----------------------------------------------------

    def parse(self) -> None:
        while self._peek() is not None:
            t = self._peek()
            assert t is not None
            if t.kind == "DIRECTIVE":
                self._parse_directive()
            elif t.kind == "IDENT":
                self._parse_rule()
            else:
                raise ParseError(
                    f"unexpected token {t.value!r}",
                    SourceLocation(line=t.line, column=t.col),
                )

    def _parse_directive(self) -> None:
        t = self._eat("DIRECTIVE")
        name = t.value[1:]
        if name == "start":
            ident = self._eat("IDENT")
            self.start = ident.value
            self._accept("SEMI")
        elif name == "token":
            ident = self._eat("IDENT")
            self._eat("EQ")
            pat = self._eat("STRING")
            self.token_rules.append((ident.value, _unquote(pat.value)))
            self._accept("SEMI")
        elif name == "skip":
            ident = self._eat("IDENT")
            self._eat("EQ")
            pat = self._eat("STRING")
            self.skip_rules.append((ident.value, _unquote(pat.value)))
            self._accept("SEMI")
        else:
            raise ParseError(
                f"unknown directive %{name}",
                SourceLocation(line=t.line, column=t.col),
            )

    def _parse_rule(self) -> None:
        head = self._eat("IDENT").value
        self._eat("ARROW")
        if self.start is None:
            self.start = head
        while True:
            body, action_src = self._parse_alt()
            self.productions.append((head, body, action_src))
            if self._accept("PIPE") is None:
                break
        self._eat("SEMI")

    def _parse_alt(self) -> tuple[list[_EBNFNode], str | None]:
        nodes: list[_EBNFNode] = []
        while True:
            t = self._peek()
            if t is None or t.kind in ("PIPE", "SEMI", "ACTION"):
                break
            nodes.append(self._parse_postfix())
        action_src: str | None = None
        t = self._peek()
        if t is not None and t.kind == "ACTION":
            self.pos += 1
            action_src = t.value
        return nodes, action_src

    def _parse_postfix(self) -> _EBNFNode:
        atom = self._parse_atom()
        t = self._peek()
        if t is not None and t.kind in ("STAR", "PLUS", "QMARK"):
            self.pos += 1
            op_map = {"STAR": "star", "PLUS": "plus", "QMARK": "opt"}
            return _EBNFNode(kind=op_map[t.kind], children=[atom])
        return atom

    def _parse_atom(self) -> _EBNFNode:
        t = self._peek()
        if t is None:
            raise ParseError("unexpected end of grammar", SourceLocation())
        if t.kind == "IDENT":
            self.pos += 1
            if t.value in ("epsilon", "\u03b5", "EPSILON"):
                return _EBNFNode(kind="eps")
            return _EBNFNode(kind="sym", value=t.value)
        if t.kind == "STRING":
            self.pos += 1
            return _EBNFNode(kind="term", value=_unquote(t.value))
        if t.kind == "LPAREN":
            self.pos += 1
            # A group can contain one or more alternatives joined by |.
            group = _EBNFNode(kind="group", children=[])
            cur: list[_EBNFNode] = []
            while True:
                p = self._peek()
                if p is None:
                    raise ParseError(
                        "unclosed '(' in grammar", SourceLocation()
                    )
                if p.kind == "RPAREN":
                    self.pos += 1
                    break
                if p.kind == "PIPE":
                    self.pos += 1
                    group.children.append(_EBNFNode(kind="seq", children=cur))
                    cur = []
                    continue
                cur.append(self._parse_postfix())
            group.children.append(_EBNFNode(kind="seq", children=cur))
            return group
        raise ParseError(
            f"unexpected token {t.value!r} in production body",
            SourceLocation(line=t.line, column=t.col),
        )

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "0": "\0",
    "\\": "\\",
    "'": "'",
    '"': '"',
}


def _unquote(literal: str) -> str:
    """Remove surrounding quotes and decode backslash escapes.

    Only decodes a minimal, well-defined escape set (``\\n \\t \\r \\0
    \\\\ \\' \\"``).  Any other backslash is preserved verbatim — this is
    important because terminals in ``%token NAME = "..."`` declarations
    are regular expressions and must keep escapes like ``\\s``, ``\\+``
    untouched.
    """

    inner = literal[1:-1]
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            esc = inner[i + 1]
            if esc in _ESCAPES:
                out.append(_ESCAPES[esc])
                i += 2
                continue
            out.append("\\")
            out.append(esc)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Semantic-action compilation
# ---------------------------------------------------------------------------


_ACTION_DOLLAR_N = re.compile(r"\$(\d+)")


def compile_action(source: str) -> Action:
    """Compile a Bison-style action body into a Python callable.

    ``$$`` denotes the produced value; ``$1..$N`` denote children values.
    Example::

        $$ = $1 + $3

    becomes::

        def action(values):
            __result = None
            __result = values[0] + values[2]
            return __result
    """

    transformed = _ACTION_DOLLAR_N.sub(
        lambda m: f"values[{int(m.group(1)) - 1}]", source
    )
    transformed = transformed.replace("$$", "__result")
    body = transformed.strip()
    if not body:
        raise ValueError("empty action block")
    code = "def __action(values):\n    __result = None\n"
    for line in body.splitlines() or [body]:
        code += f"    {line.strip()}\n"
    code += "    return __result\n"
    ns: dict[str, Any] = {}
    exec(compile(code, "<grammar-action>", "exec"), ns)
    return ns["__action"]


# ---------------------------------------------------------------------------
# Public DSL entry points
# ---------------------------------------------------------------------------


@dataclass
class DSLResult:
    """Parsed DSL output: a :class:`Grammar` plus optional lexer rules."""

    grammar: Grammar
    token_rules: list[tuple[str, str]] = field(default_factory=list)
    skip_rules: list[tuple[str, str]] = field(default_factory=list)


def parse_grammar(
    source: str, *, start: str | None = None
) -> DSLResult:
    """Parse a DSL source string into a :class:`Grammar`."""

    from .transforms import desugar_ebnf  # local import to avoid cycle

    toks = _tokenize_dsl(source)
    dsl = _DSLParser(toks)
    dsl.parse()
    effective_start = start or dsl.start
    if effective_start is None:
        raise ValueError("grammar has no rules")

    rules: dict[str, list[list[str]]] = {}
    actions: dict[tuple[str, tuple[str, ...]], Action] = {}
    counter = [0]

    def fresh(base: str) -> str:
        counter[0] += 1
        return f"{base}__{counter[0]}"

    def emit(head: str, body: list[str]) -> None:
        rules.setdefault(head, []).append(body)

    for head, alt_nodes, action_src in dsl.productions:
        body = desugar_ebnf(alt_nodes, head, emit, fresh)
        emit(head, body)
        if action_src is not None:
            action = compile_action(action_src)
            actions[(head, tuple(body) if body != [EPSILON] else ())] = action

    grammar = Grammar.from_rules(effective_start, rules, actions=actions)
    return DSLResult(
        grammar=grammar,
        token_rules=list(dsl.token_rules),
        skip_rules=list(dsl.skip_rules),
    )


def parse_grammar_file(
    path: str | os.PathLike[str], *, start: str | None = None
) -> DSLResult:
    """Read a grammar file from disk and parse it."""

    with open(path, encoding="utf-8") as fh:
        return parse_grammar(fh.read(), start=start)


def parse_production_string(spec: str) -> tuple[str, tuple[str, ...]]:
    """Parse a single ``head -> body`` spec (used by ``@parser.action``).

    Example::

        parse_production_string("Expr -> Term '+' Expr")
        # -> ("Expr", ("Term", "+", "Expr"))
    """

    toks = _tokenize_dsl(spec + " ;")
    p = _DSLParser(toks)
    head_tok = p._eat("IDENT")
    p._eat("ARROW")
    body, _ = p._parse_alt()
    # Body must be a flat sequence of sym/term/eps for this shortcut.
    out: list[str] = []
    for node in body:
        if node.kind == "sym" or node.kind == "term":
            out.append(str(node.value))
        elif node.kind == "eps":
            pass
        else:
            raise ValueError(
                "parse_production_string does not support EBNF sugar"
            )
    return head_tok.value, tuple(out)


__all__ = [
    "DSLResult",
    "Grammar",
    "compile_action",
    "parse_grammar",
    "parse_grammar_file",
    "parse_production_string",
]
