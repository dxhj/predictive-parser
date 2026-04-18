# Concepts

## LL(1) Parsing

**LL(1)** means *left-to-right* input, *leftmost* derivation, *1* token of
lookahead.  At each step, given the nonterminal on top of the stack and
the current input token, there is exactly one production that could
possibly produce a match.  This lets the parser decide deterministically
without backtracking.

Not every grammar is LL(1).  Grammars with left recursion or common
prefixes between alternatives are not, but many can be mechanically
transformed into LL(1) form.  See
[`eliminate_left_recursion`](../predictive_parser/transforms.py) and
[`left_factor`](../predictive_parser/transforms.py).

## Terminals, Nonterminals, and ε

- **Terminals** are the atomic input tokens (e.g. `id`, `+`).
- **Nonterminals** are rule names (e.g. `Expr`, `Term`) — every key in
  the grammar dict is a nonterminal.
- **ε (epsilon)** denotes the empty string.  A rule `Exprp -> ε` means
  "Exprp can produce nothing."  In this library ε is the empty string
  literal (`""`) exported as `EPSILON`.

## FIRST, FOLLOW, NULLABLE

Three derived sets drive LL(1) table construction:

- `NULLABLE(X)` — `True` if `X` can derive ε.
- `FIRST(X)` — the set of terminals that can begin a string derived from `X`.
- `FOLLOW(A)` — the set of terminals that can appear immediately after `A`
  in any derivation.

Each is computed as a fixed point over the grammar.  Given these, a
cell `Table[A, t]` is populated when terminal `t ∈ FIRST(α)` for a
production `A -> α`, plus the FOLLOW set when the body is nullable.

## The `$` Endmarker

`$` is a pseudo-terminal appended to the token stream that represents
*end of input*.  It is used to populate FOLLOW(start) and to recognize
successful acceptance.  Users never write `$` in their own grammar —
the parser adds it automatically.

## Uppercase-Nonterminal Convention

When you construct a parser from a plain Python dict, the library uses a
simple heuristic to validate that every uppercase symbol on a right-hand
side has a rule somewhere.  You can bypass that heuristic by declaring
terminals explicitly via `%token NAME = "..."` in the DSL — any symbol
declared as a terminal is exempt from the uppercase rule.

## LL(k) Lookahead

Fixed-`k` lookahead resolves some LL(1) conflicts.  Construct a parser
with `PredictiveParser.from_grammar(src, k=2)` and the alternative
selection will consult up to two tokens when deciding which production
to expand.  `k=1` (the default) is equivalent to the classic LL(1)
prediction table.

## Parse Tree vs Semantic Value

When no user action is attached to a production, the default behavior
builds a [`ParseTree`](../predictive_parser/tree.py) node holding the
production's children verbatim.  When you attach actions, each action's
return value propagates up the value stack — the final value is whatever
the start-symbol's action returned.

## Error Listeners

An `ErrorListener` is a pluggable callback invoked on each syntax error.
The default (`RaisingErrorListener`) raises `ParseError` on the first
issue.  `DefaultErrorListener` collects errors without raising, which is
useful for IDE-style diagnostics where you want to report multiple
issues per parse.
