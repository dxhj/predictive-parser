# Tutorial: Building a Calculator Parser

This tutorial walks through creating a small arithmetic expression parser
and evaluator using the grammar DSL, a lexer, and semantic actions.

## Step 1 — Define the grammar

We want to handle integers, `+`, `*`, and parentheses, with standard
precedence.  The classic LL(1)-friendly expression grammar is:

```text
Expr   -> Term Exprp
Exprp  -> '+' Term Exprp | ε
Term   -> Factor Termp
Termp  -> '*' Factor Termp | ε
Factor -> '(' Expr ')' | NUM
```

`Exprp` and `Termp` are "primed" helper nonterminals that break left
recursion.  Any textbook expression-grammar chapter explains the
transformation.

## Step 2 — Attach a lexer

Declare tokens and the whitespace-skip rule directly in the grammar file:

```text
%skip  WS   = "\s+"
%token NUM  = "[0-9]+"
%token PLUS = "\+"
%token STAR = "\*"
%token LP   = "\("
%token RP   = "\)"
```

`%skip` rules are matched and consumed but produce no token (perfect for
whitespace and comments).

## Step 3 — Add semantic actions

Inline Bison-style actions go in `{ ... }` after each alternative.
`$N` refers to the N-th child's value (1-indexed), `$$` is this
production's result.

```text
Expr   -> Term Exprp         { $$ = $1 + $2 } ;
Exprp  -> PLUS Term Exprp    { $$ = $2 + $3 }
       |  epsilon            { $$ = 0 } ;
Term   -> Factor Termp       { $$ = $1 * ($2 or 1) } ;
Termp  -> STAR Factor Termp  { $$ = $2 * ($3 or 1) }
       |  epsilon            { $$ = 0 } ;
Factor -> LP Expr RP         { $$ = $2 }
       |  NUM                { $$ = int($1.value) } ;
```

## Step 4 — Use it

```python
from predictive_parser import PredictiveParser

calc = PredictiveParser.from_grammar_file("calc.gr")
assert calc.parse_text("1 + 2 * 3") == 7
assert calc.parse_text("(1 + 2) * 3") == 9
```

## Alternative — decorator-based actions

If you prefer pure Python over inline actions, register decorators:

```python
parser = PredictiveParser.from_grammar_file("calc.gr")

@parser.action("Factor -> NUM")
def factor_num(v):
    return int(v[0].value)

@parser.action("Expr -> Term Exprp")
def expr_add(v):
    return v[0] + v[1]
```

## Error reporting

Syntax errors carry a [`SourceLocation`](concepts.md) so you can build
editor-quality diagnostics:

```python
from predictive_parser import ParseError
try:
    calc.parse_text("1 + ")
except ParseError as e:
    print(f"{e.location}: {e}")
# line 1, column 5: no derivation for Expr on `$`
```

## Streaming inputs

The parser accepts any iterator, so you can pipe tokens from a socket,
a REPL, or a generator without buffering the whole input:

```python
def tokens():
    yield "NUM"
    yield "PLUS"
    yield "NUM"

calc.parse(tokens())
```
