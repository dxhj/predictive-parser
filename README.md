# predictive-parser

A compact, dependency-free LL(1) predictive parser toolkit for Python.

Ships with a regex-based **lexer**, a **parse-tree** builder, **semantic
actions**, an EBNF **grammar DSL**, a **CLI**, and grammar transformations
(left-factoring, left-recursion elimination).  The parser is lexer-agnostic
and stream-friendly — you can drive it from any iterator of tokens.

---

## Installation

```bash
pip install predictive-parser
```

Requires Python 3.10+.

## Quick start — three layers of API

### 1. Plain dict grammar, recognize-only

```python
from predictive_parser import PredictiveParser, EPSILON

parser = PredictiveParser("E", {
    "E":  [["T", "Ep"]],
    "Ep": [["+", "T", "Ep"], [EPSILON]],
    "T":  [["F", "Tp"]],
    "Tp": [["*", "F", "Tp"], [EPSILON]],
    "F":  [["(", "E", ")"], ["id"]],
})

parser.match(["id", "+", "id", "*", "id"])          # True
parser.detailed_match(["+"])
# MatchResult(success=False, position=0, expected={'(', 'id'}, got='+')
```

### 2. Parse to a tree

```python
tree = parser.parse(["id", "+", "id"])
print(tree.pretty())
#  E
#    T
#      F
#        id
#      Tp
#    Ep
#      +
#      T
#        F
#          id
#        Tp
#      Ep
```

### 3. Grammar DSL + semantic actions — build a calculator

```python
from predictive_parser import PredictiveParser

source = r"""
%skip  WS    = "\s+"
%token NUM   = "[0-9]+"
%token PLUS  = "\+"
%token STAR  = "\*"
%token LP    = "\("
%token RP    = "\)"

Expr   -> Term Exprp        { $$ = $1 + $2 } ;
Exprp  -> PLUS Term Exprp   { $$ = $2 + $3 }
       |  epsilon           { $$ = 0 } ;
Term   -> Factor Termp      { $$ = $1 * ($2 or 1) } ;
Termp  -> STAR Factor Termp { $$ = $2 * ($3 or 1) }
       |  epsilon           { $$ = 0 } ;
Factor -> LP Expr RP        { $$ = $2 }
       |  NUM               { $$ = int($1.value) } ;
"""
calc = PredictiveParser.from_grammar(source)
calc.parse_text("2 + 3 * 4")   # 14
```

## Features

- **LL(1) parsing** with FIRST/FOLLOW-based prediction table
- **Optional LL(k)** mode for length-bounded lookahead
- **Streaming input** — parse from any iterator, no pre-buffering required
- **Built-in regex lexer** or bring your own (PLY-compatible adapter included)
- **Parse trees** with visitor/listener traversal
- **Semantic actions** per production (decorator or Bison-style inline `$$ / $N`)
- **Grammar DSL** supporting BNF (`->`, `::=`, `:`) and EBNF (`?`, `*`, `+`, groups)
- **Grammar transforms** — automatic left-factoring and left-recursion elimination
- **Rich error reporting** with source locations and pluggable error listeners
- **Serialization** — dump/load precomputed parse tables as JSON
- **CLI** — `predictive-parser check grammar.gr`, `parse`, `first`, `follow`, `dump`
- **Fully typed** (PEP 561 `py.typed` marker)

## CLI

```text
$ predictive-parser check grammar.gr
start: Expr
terminals: ['NUM', 'PLUS', 'RP']
nonterminals: ['Expr', 'Exprp']
parse table:
  (Expr, NUM) -> Term Exprp
  ...

$ predictive-parser parse grammar.gr input.txt
$ predictive-parser dump  grammar.gr tables.json
```

## Documentation

- **[Tutorial](docs/tutorial.md)** — build a calculator parser from scratch.
- **[Concepts](docs/concepts.md)** — LL(1), FIRST / FOLLOW, ε, the `$` endmarker.
- **[Grammar reference](docs/grammar.md)** — DSL syntax, EBNF, actions.
- **[Semantic actions](docs/actions.md)** — inline `{ ... }`, decorators, defaults, `ActionError`.

## Backward compatibility

Version 2 preserves the legacy `from predictive import PredictiveParser`
import.  Existing 1.x code continues to work unchanged.

## Contributing

Pull requests welcome.  Install the dev extras and run the test suite:

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy
```

## License

GPL-3.0-or-later.  See [LICENSE](LICENSE).
