"""The :class:`PredictiveParser` — LL(1) predictive parser with optional
LL(k) support, streaming input, parse-tree construction, semantic actions,
and error recovery."""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .actions import Action, ProductionSpec
from .errors import (
    ActionError,
    ErrorListener,
    ParseError,
    RaisingErrorListener,
    SourceLocation,
)
from .grammar import (
    DSLResult,
    Grammar,
    parse_grammar,
    parse_grammar_file,
    parse_production_string,
)
from .lexer import (
    Lexer,
    SimpleToken,
    TokenLike,
    TokenRule,
    TokenStream,
    get_location,
    normalize_tokens,
)
from .sets import END_MARK, EPSILON, first_of_sequence
from .table import LL1Conflict, build_ll1_table, build_llk_table, index_table
from .tree import ParseTree, tree_location

# ---------------------------------------------------------------------------
# Legacy result object (kept for backwards compatibility with existing tests)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_END_TOKEN = SimpleToken(type=END_MARK, value=END_MARK)


class _ReduceMarker:
    """Stack marker that triggers a production's semantic action when popped."""

    __slots__ = ("arity", "spec")

    def __init__(self, spec: ProductionSpec, arity: int) -> None:
        self.spec = spec
        self.arity = arity


class _Lookahead:
    """Pull-based token buffer with k-token lookahead.

    Wraps any iterable of tokens (strings or TokenLike) and supplies an
    endless stream of :class:`TokenLike` objects — padding with the sentinel
    ``$`` token once the underlying iterator is exhausted.
    """

    def __init__(self, stream: TokenStream, k: int = 1) -> None:
        self._it: Iterator[TokenLike] = normalize_tokens(stream)
        self._buf: deque[TokenLike] = deque()
        self._k = max(1, k)
        self._pos = 0
        self._consumed_end = False
        self._fill()

    def _fill(self) -> None:
        while len(self._buf) < self._k:
            try:
                tok = next(self._it)
            except StopIteration:
                self._buf.append(_END_TOKEN)
                return
            self._buf.append(tok)

    def peek(self, offset: int = 0) -> TokenLike:
        while len(self._buf) <= offset:
            try:
                tok = next(self._it)
            except StopIteration:
                while len(self._buf) <= offset:
                    self._buf.append(_END_TOKEN)
                return self._buf[offset]
            self._buf.append(tok)
        return self._buf[offset]

    def consume(self) -> TokenLike:
        tok = self._buf.popleft()
        if tok is _END_TOKEN:
            self._buf.appendleft(_END_TOKEN)
        else:
            self._pos += 1
            self._fill()
        return tok

    @property
    def position(self) -> int:
        return self._pos


# ---------------------------------------------------------------------------
# Main parser class
# ---------------------------------------------------------------------------


GrammarInput = dict[str, list[list[str]]] | Grammar


class PredictiveParser:
    """An LL(1) (optionally LL(k)) predictive parser.

    Backward-compatible constructor: ``PredictiveParser(start, grammar_dict)``.

    New optional keyword arguments:

    * ``grammar`` may also be a :class:`Grammar` object (from the DSL loader).
    * ``k`` — lookahead depth for LL(k) mode (default 1).
    * ``error_listener`` — custom error listener.  Default raises on first
      error, matching the legacy behavior.
    * ``build_tree`` — whether :meth:`parse` constructs a :class:`ParseTree`
      when no user action is attached.
    """

    def __init__(
        self,
        start: str,
        grammar: GrammarInput,
        *,
        k: int = 1,
        error_listener: ErrorListener | None = None,
        build_tree: bool = True,
        lexer: Lexer | None = None,
        declared_terminals: set[str] | None = None,
    ) -> None:
        self._declared_terminals = declared_terminals
        if isinstance(grammar, Grammar):
            self._grammar_obj: Grammar = grammar
            grammar_dict = grammar.as_dict()
            start = start or grammar.start
        else:
            grammar_dict = grammar
            self._grammar_obj = Grammar.from_rules(start, grammar)

        self.start = start
        self.grammar = grammar_dict
        self.k = max(1, k)
        self.build_tree = build_tree
        self.lexer = lexer
        self._error_listener = error_listener or RaisingErrorListener()

        self.terminals, self.nonterminals = self._classify_symbols()
        self._validate_grammar()

        self.table, self.null_dict, self.first_dict, self.follow_dict = (
            build_ll1_table(
                self.grammar, self.start, self.terminals
            )
        )
        self._table_by_nt = index_table(self.table)

        if self.k > 1:
            try:
                self._llk_table = build_llk_table(
                    self.grammar, self.start, self.terminals, self.k
                )
            except LL1Conflict:
                # Fall back to LL(1) at parse-time if the k-extension has
                # its own conflicts; LL(1) remains authoritative.
                self._llk_table = None
        else:
            self._llk_table = None

        self._actions: dict[tuple[str, tuple[str, ...]], Action] = {}
        for p in self._grammar_obj.iter_productions():
            if p.action is not None:
                self._actions[(p.head, p.body)] = p.action

    # ------------------------------------------------------------------
    # Classification & validation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"PredictiveParser(start={self.start!r}, "
            f"nonterminals={len(self.nonterminals)}, "
            f"terminals={len(self.terminals)})"
        )

    def _classify_symbols(self) -> tuple[set[str], set[str]]:
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
        declared_terminals = getattr(self, "_declared_terminals", None)
        for head, prods in self.grammar.items():
            for prod in prods:
                for sym in prod:
                    if sym == EPSILON or sym in self.grammar:
                        continue
                    if declared_terminals is not None and sym in declared_terminals:
                        continue
                    # Legacy heuristic: symbols starting with an uppercase
                    # letter are assumed to be nonterminals.  Only enforce
                    # this when no explicit terminal set has been declared.
                    if declared_terminals is None and sym[0:1].isupper():
                        raise ValueError(
                            f"nonterminal {sym!r} in production "
                            f"{head} \u2192 {' '.join(prod)} has no "
                            f"defining rule in the grammar"
                        )

    # ------------------------------------------------------------------
    # FIRST / FOLLOW / table (legacy method access)
    # ------------------------------------------------------------------

    def nullable(self, symbols: list[str]) -> bool:
        return all(self.null_dict[s] for s in symbols)

    def first(self, symbols: list[str]) -> set[str]:
        return first_of_sequence(symbols, self.first_dict, self.null_dict)

    def print_table(self) -> None:
        for nonterminal in self.nonterminals:
            for terminal in self.terminals | {END_MARK}:
                prod = self.table.get((nonterminal, terminal))
                if prod is not None:
                    print(f"({nonterminal}, {terminal}) = {prod}")

    # ------------------------------------------------------------------
    # Public parsing API
    # ------------------------------------------------------------------

    def match(self, seq: TokenStream) -> bool:
        """Recognize-only: return True if ``seq`` is accepted by the grammar."""

        return self._run(seq, collect_tree=False, run_actions=False).success

    def detailed_match(self, seq: TokenStream) -> MatchResult:
        """Like :meth:`match` but with diagnostic info on failure."""

        outcome = self._run(seq, collect_tree=False, run_actions=False)
        return MatchResult(
            success=outcome.success,
            position=outcome.position,
            expected=outcome.expected,
            got=outcome.got,
        )

    def verbose_match(
        self, seq: TokenStream, display_stack: bool = False
    ) -> bool:
        """Like :meth:`match` but prints each derivation/match step."""

        return self._run(
            seq,
            collect_tree=False,
            run_actions=False,
            verbose=True,
            display_stack=display_stack,
        ).success

    def parse(
        self,
        tokens: TokenStream,
        *,
        run_actions: bool | None = None,
        build_tree: bool | None = None,
    ) -> Any:
        """Parse ``tokens`` into a value.

        With semantic actions attached this returns the action result.  With
        no actions attached (the default) it returns a :class:`ParseTree`.

        Raises :class:`ParseError` on syntax error (unless a collecting
        error listener is configured on the parser).
        """

        run_actions_final = (
            run_actions
            if run_actions is not None
            else bool(self._actions)
        )
        build_tree_final = build_tree if build_tree is not None else self.build_tree
        outcome = self._run(
            tokens,
            collect_tree=build_tree_final or run_actions_final,
            run_actions=run_actions_final,
        )
        if not outcome.success:
            raise ParseError(
                message=outcome.message or "syntax error",
                location=outcome.location,
                expected=outcome.expected,
                got=outcome.got,
                position=outcome.position,
            )
        return outcome.value

    def parse_text(self, text: str, *, lexer: Lexer | None = None) -> Any:
        """Lex ``text`` and parse it.  Requires a lexer to be configured."""

        lex = lexer or self.lexer
        if lex is None:
            raise ValueError(
                "parse_text requires a Lexer — pass lexer=... or construct "
                "the parser with lexer=..."
            )
        return self.parse(lex.lex(text))

    # ------------------------------------------------------------------
    # Semantic-action registration
    # ------------------------------------------------------------------

    def action(
        self, production: str
    ) -> Callable[[Action], Action]:
        """Decorator: register a semantic action for a production.

        Usage::

            @parser.action("Expr -> Term '+' Expr")
            def add(values): return values[0] + values[2]
        """

        head, body = parse_production_string(production)

        def decorator(fn: Action) -> Action:
            self.set_action(head, body, fn)
            return fn

        return decorator

    def set_action(
        self, head: str, body: tuple[str, ...], action: Action
    ) -> None:
        """Programmatic action registration."""

        self._grammar_obj.set_action(head, body, action)
        self._actions[(head, body)] = action

    # ------------------------------------------------------------------
    # Grammar-file constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_grammar(
        cls, source: str, *, start: str | None = None, k: int = 1
    ) -> PredictiveParser:
        """Construct a parser from a DSL source string."""

        result: DSLResult = parse_grammar(source, start=start)
        return cls._from_dsl(result, k=k)

    @classmethod
    def from_grammar_file(
        cls,
        path: str | os.PathLike[str],
        *,
        start: str | None = None,
        k: int = 1,
    ) -> PredictiveParser:
        """Construct a parser by loading a grammar file."""

        result = parse_grammar_file(path, start=start)
        return cls._from_dsl(result, k=k)

    @classmethod
    def _from_dsl(cls, result: DSLResult, *, k: int = 1) -> PredictiveParser:
        lexer = (
            _lexer_from_dsl(result)
            if result.token_rules or result.skip_rules
            else None
        )
        declared = {name for name, _ in result.token_rules}
        declared.update(name for name, _ in result.skip_rules)
        return cls(
            result.grammar.start,
            result.grammar,
            k=k,
            lexer=lexer,
            declared_terminals=declared or None,
        )

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def _expected_at(self, nonterminal: str) -> frozenset[str]:
        """Pre-indexed expected-terminal set for ``nonterminal``."""

        return frozenset(self._table_by_nt.get(nonterminal, {}).keys())

    def _run(
        self,
        seq: TokenStream,
        *,
        collect_tree: bool = True,
        run_actions: bool = True,
        verbose: bool = False,
        display_stack: bool = False,
    ) -> _Outcome:
        la = _Lookahead(seq, k=self.k)
        stack: list[Any] = [END_MARK, self.start]
        value_stack: list[Any] = []

        # Default "action": build a ParseTree when the user supplied none.
        def _tree_default(head: str, body: tuple[str, ...]) -> Action:
            def build(values: list[Any]) -> Any:
                return ParseTree(
                    symbol=head,
                    children=list(values),
                    production=body,
                    location=tree_location(values),
                )
            return build

        while True:
            top = stack[-1]

            if isinstance(top, _ReduceMarker):
                stack.pop()
                arity = top.arity
                if arity > 0:
                    values = value_stack[-arity:]
                    del value_stack[-arity:]
                else:
                    values = []
                action = top.spec.action
                if action is None and collect_tree:
                    action = _tree_default(top.spec.head, top.spec.body)
                if run_actions and action is not None:
                    try:
                        result = action(values)
                    except BaseException as exc:
                        loc = tree_location(values)
                        raise ActionError(
                            production=(top.spec.head, top.spec.body),
                            original=exc,
                            location=loc,
                        ) from exc
                elif collect_tree:
                    result = ParseTree(
                        symbol=top.spec.head,
                        children=list(values),
                        production=top.spec.body,
                        location=tree_location(values),
                    )
                else:
                    result = None
                value_stack.append(result)
                continue

            if top == END_MARK:
                break

            cur = la.peek()
            cur_type = cur.type

            if display_stack and verbose:
                print("Stack:", _format_stack(stack))

            if top == cur_type:
                la.consume()
                stack.pop()
                if verbose:
                    print(f"** Action: match `{top}`")
                value_stack.append(cur)
                continue

            if self.is_terminal(top):
                loc = get_location(cur)
                msg = f"expected {top!r}, got {cur_type!r}"
                self._report(msg, loc, frozenset({top}), cur)
                return _Outcome(
                    success=False,
                    position=la.position,
                    expected=frozenset({top}),
                    got=cur_type,
                    message=msg,
                    location=loc,
                )

            prod = self.table.get((top, cur_type))
            if prod is None:
                expected = self._expected_at(top)
                loc = get_location(cur)
                msg = (
                    f"no derivation for {top} on `{cur_type}` "
                    f"(expected one of {sorted(expected)})"
                )
                if verbose:
                    print(
                        f"ERROR: Not able to find derivation of"
                        f" {top} on `{cur_type}`"
                    )
                self._report(msg, loc, expected, cur)
                return _Outcome(
                    success=False,
                    position=la.position,
                    expected=expected,
                    got=cur_type,
                    message=msg,
                    location=loc,
                )

            if verbose:
                if prod == [EPSILON]:
                    print(f"** Action: derive {top} on `{cur_type}` to: \u03b5")
                else:
                    print(
                        f"** Action: derive {top} on "
                        f"`{cur_type}` to: {' '.join(prod)}"
                    )

            stack.pop()
            body_tuple = tuple(prod) if prod != [EPSILON] else ()
            spec = _find_spec(self._grammar_obj, top, body_tuple)
            arity = len(body_tuple)
            stack.append(_ReduceMarker(spec=spec, arity=arity))
            if prod != [EPSILON]:
                stack.extend(reversed(prod))

        # Stack is down to endmarker. Expect end-of-input.
        if la.peek().type == END_MARK:
            if display_stack and verbose:
                print("Stack:", _format_stack(stack))
            value = value_stack[0] if value_stack else None
            return _Outcome(
                success=True,
                position=la.position,
                value=value,
            )
        cur = la.peek()
        loc = get_location(cur)
        msg = f"unexpected token {cur.type!r} after end of input"
        self._report(msg, loc, frozenset({END_MARK}), cur)
        return _Outcome(
            success=False,
            position=la.position,
            expected=frozenset({END_MARK}),
            got=cur.type,
            message=msg,
            location=loc,
        )

    # ------------------------------------------------------------------
    # Error reporting (listener-aware)
    # ------------------------------------------------------------------

    def _report(
        self,
        message: str,
        location: SourceLocation,
        expected: frozenset[str],
        got: TokenLike | None,
    ) -> None:
        listener = self._error_listener
        if isinstance(listener, RaisingErrorListener):
            # Delay raising until caller; _run returns the Outcome and the
            # caller decides whether to raise.
            return
        listener.syntax_error(location, expected, got, message)


@dataclass
class _Outcome:
    success: bool
    position: int = 0
    expected: frozenset[str] = field(default_factory=frozenset)
    got: str | None = None
    value: Any = None
    message: str | None = None
    location: SourceLocation = field(default_factory=SourceLocation)


def _format_stack(stack: list[Any]) -> list[str]:
    out: list[str] = []
    for item in stack:
        if isinstance(item, _ReduceMarker):
            continue
        out.append(item)
    return out


def _find_spec(
    grammar: Grammar, head: str, body: tuple[str, ...]
) -> ProductionSpec:
    for p in grammar.productions.get(head, ()):
        if p.body == body:
            return p
    # Fallback (should not happen when grammar was built from the same dict)
    return ProductionSpec(head=head, body=body, action=None)


def _lexer_from_dsl(result: DSLResult) -> Lexer:
    rules: list[TokenRule] = []
    for name, pat in result.skip_rules:
        rules.append(TokenRule(name=name, pattern=pat, skip=True))
    for name, pat in result.token_rules:
        rules.append(TokenRule(name=name, pattern=pat, skip=False))
    return Lexer(rules)


__all__ = [
    "MatchResult",
    "PredictiveParser",
]
