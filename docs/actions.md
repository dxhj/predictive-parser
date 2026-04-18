# Semantic Actions

A **semantic action** is a Python callable the parser runs every time it
finishes recognising a production.  Its return value is pushed onto an
internal *value stack* and becomes an input to the action of the enclosing
production, so values flow bottom-up through the derivation.  When parsing
succeeds, the value returned by the start symbol's action is what
`parser.parse(...)` / `parser.parse_text(...)` hands back.

Actions are where you turn a derivation into something useful — a number,
an AST node, a symbol-table entry, IR for a compiler, a JSON object, and
so on.

## The `Action` type

```python
from predictive_parser import Action

Action = Callable[[list[Any]], Any]
```

Every action receives a single argument: the list of children values in
left-to-right order.  For a production `A -> X Y Z`, `values[0]` is the
value produced by `X`, `values[1]` by `Y`, and so on.  For an
ε-production, `values` is `[]`.

What goes into `values` depends on what the child symbol is:

- **Terminal** — the token object emitted by the lexer.  With the
  built-in `Lexer`, that's a `Token` with `.type`, `.value`, `.location`.
  If you drive the parser from a plain iterator of strings, the value is
  the string itself.
- **Nonterminal** — whatever that nonterminal's action returned.  If no
  action was registered for it, the default behavior kicks in (see
  [Default behaviors](#default-behaviors)).

## Three ways to attach actions

### 1. Inline, Bison-style, in the DSL

Write a Python expression block in `{ ... }` after each alternative.
`$$` is the value this production produces; `$1`, `$2`, ... are the
children (1-indexed).

```text
Expr   -> Term Exprp         { $$ = $1 + $2 } ;
Exprp  -> PLUS Term Exprp    { $$ = $2 + $3 }
       |  epsilon            { $$ = 0 } ;
Factor -> LP Expr RP         { $$ = $2 }
       |  NUM                { $$ = int($1.value) } ;
```

The block may span multiple statements — the last `$$ = ...` wins:

```text
Stmt -> IF Expr THEN Stmt {
    cond = $2
    body = $4
    $$ = ("if", cond, body)
} ;
```

Under the hood, [`compile_action`](../predictive_parser/grammar.py)
rewrites `$$` / `$N` and compiles the block into a Python function once
at grammar-load time.  You can call it directly if you want to inspect
the result:

```python
from predictive_parser import compile_action

fn = compile_action("$$ = $1 + $3")
fn([2, "+", 3])   # 5
```

### 2. The `@parser.action(...)` decorator

Prefer plain Python for complex logic?  Register an action per
production with its `head -> body` string:

```python
from predictive_parser import PredictiveParser

parser = PredictiveParser.from_grammar_file("calc.gr")

@parser.action("Factor -> NUM")
def factor_num(values):
    return int(values[0].value)

@parser.action("Expr -> Term Exprp")
def expr_add(values):
    left, tail = values
    return left + tail
```

The body is matched against the actual grammar after EBNF desugaring —
if the production was written as `X -> Y Z?`, the rule registered under
the fresh helper nonterminal (e.g. `X__1`) is the one the parser will
actually call.  Use `parser.grammar` to see the desugared rules.

Terminal literals in the body may be spelled with single or double
quotes, matching the DSL syntax:

```python
@parser.action("Expr -> Term '+' Expr")
def add(values):
    return values[0] + values[2]
```

### 3. Programmatic registration

For code-generation or dynamic grammars, register actions through the
lower-level API:

```python
parser.set_action(
    head="Factor",
    body=("NUM",),
    action=lambda v: int(v[0].value),
)
```

Or attach actions directly to a `Grammar` at construction:

```python
from predictive_parser import Grammar, PredictiveParser

grammar = Grammar.from_rules(
    start="Expr",
    rules={"Expr": [["NUM"]]},
    actions={("Expr", ("NUM",)): lambda v: int(v[0])},
)
parser = PredictiveParser("Expr", grammar)
```

## `ProductionSpec`

Every action is stored against a [`ProductionSpec`](../predictive_parser/actions.py):

```python
@dataclass
class ProductionSpec:
    head: str
    body: tuple[str, ...]
    action: Action | None = None
    source_line: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
```

- `head` / `body` identify the production (body `()` for ε).
- `action` is `None` to keep the default behavior.
- `source_line` and `attributes` are metadata slots that DSL-based
  constructors fill in for diagnostics and future extensions.  They are
  never required.

`ProductionSpec.key()` returns `(head, body)` — handy when you want to
key a user dict by production.

## Default behaviors

When a production has **no** action registered, the parser's behavior
depends on the call site:

- `parser.parse(...)` and `parser.parse_text(...)` **build a
  [`ParseTree`](../predictive_parser/tree.py)** node whose children are
  exactly `values`.  This is what makes the library usable as a pure
  parser, without any actions at all.
- `parser.match(...)` / `parser.detailed_match(...)` skip action
  execution entirely — they only answer "does this input derive from
  the start symbol?".

Two helpers are exported for common cases:

```python
from predictive_parser import default_action, concat_action
```

- `default_action(values)` — returns `values[0]` if non-empty, else
  `None`.  Mimics Bison's implicit `$$ = $1`.
- `concat_action(values)` — returns `tuple(values)`.  Useful for
  productions whose job is to collect children into a sequence.

Attach them like any other action:

```python
parser.set_action("ArgList", ("Expr", "COMMA", "ArgList"), concat_action)
```

## Mixed grammars

You can register actions on some productions and leave others alone — the
parser will run your action where present and fall back to tree-building
otherwise.  This is useful for partial semantics: keep the tree for
downstream tooling, but evaluate leaf nodes eagerly.

```python
@parser.action("Factor -> NUM")
def factor_num(values):
    return int(values[0].value)

tree = parser.parse_text("1 + 2 * 3")
# The Factor nodes now carry ints instead of tokens;
# the rest of the tree is still ParseTree.
```

## Error handling — `ActionError`

If an action raises, the parser catches the exception and re-raises it
wrapped in [`ActionError`](../predictive_parser/errors.py) with the
offending production and source location:

```python
from predictive_parser import ActionError

try:
    parser.parse_text(src)
except ActionError as e:
    head, body = e.production
    print(f"action for {head} -> {' '.join(body)} failed at {e.location}")
    raise e.original
```

The original exception is chained via `__cause__`, so you still see the
real traceback in an uncaught error.

## Patterns and tips

### Tokens vs. values

Children that are **terminals** are tokens, not strings.  Reach for
`.value` when you need the matched text:

```python
@parser.action("Factor -> NUM")
def factor_num(values):
    return int(values[0].value)   # not int(values[0])
```

### Epsilon productions

An ε-production's body is `()` and its action receives `values=[]`.
Make sure your action returns a well-defined "empty" — `[]`, `0`, `None`,
the identity element of your fold, etc. — because whatever you return
will be the input to the parent action.

```python
@parser.action("ArgList -> epsilon")
def arglist_empty(_):
    return []
```

### Fixing right-recursive tails

EBNF sugar (`A+`, `A*`, `(A B)`) and manually factored grammars both
tend to introduce right-recursive tail nonterminals (`Exprp`, `Termp`).
A common idiom is to have the tail return a **list of pending
operations** and let the parent fold them left-associatively so that
`1 + 2 + 3` becomes `((1 + 2) + 3)` rather than `(1 + (2 + 3))`:

```python
@parser.action("Expr -> Term Exprp")
def expr(values):
    left, tail = values
    for op, right in tail:
        left = BinOp(op, left, right)
    return left

@parser.action("Exprp -> PLUS Term Exprp")
def exprp_plus(values):
    _plus_tok, term, rest = values
    return [("+", term), *rest]

@parser.action("Exprp -> epsilon")
def exprp_empty(_):
    return []
```

See [`examples/custom_ast.py`](../examples/custom_ast.py) for a full
runnable version.

### Building ASTs cleanly

Keep the grammar *structural* (no `{ ... }` blocks) and register every
action in Python.  Your grammar file stays readable, and your AST node
classes live next to the rest of your code with type-checker support.

### Side effects

Actions are plain Python — they can mutate a shared symbol table, emit
diagnostics, or perform I/O.  The parser calls each action **exactly
once** per successful reduction, in derivation order, so using a list or
dict passed in via closure is safe.

## Execution model

1. The parser pushes reduce markers as it expands nonterminals.
2. When a marker is reached, the top `arity` values on the value stack
   become `values` for the action.
3. The action's return value replaces those children on the stack.
4. Parsing ends with exactly one value on the stack — the result of the
   start symbol's action — which `parser.parse(...)` returns.

If you construct the parser with `run_actions=False` (an internal knob
used by `match`), actions are never called and the value stack is used
only to build the parse tree.

## API summary

| Name | Role |
|---|---|
| `Action` | Type alias: `Callable[[list[Any]], Any]`. |
| `ProductionSpec` | `(head, body, action, source_line, attributes)` record. |
| `default_action` | Returns `values[0] if values else None`. |
| `concat_action` | Returns `tuple(values)`. |
| `compile_action(src)` | Compile a `$$ / $N` Bison-style body to an `Action`. |
| `parser.action(prod)` | Decorator for registering actions. |
| `parser.set_action(head, body, fn)` | Programmatic registration. |
| `Grammar.from_rules(..., actions=...)` | Attach actions at grammar construction. |
| `ActionError` | Wraps any exception raised inside an action. |

## See also

- [Grammar reference](grammar.md) — syntax of `{ ... }` blocks, `$$`,
  `$N`, EBNF desugaring rules.
- [Tutorial](tutorial.md) — end-to-end calculator using inline and
  decorator-based actions.
- [`examples/custom_ast.py`](../examples/custom_ast.py) — building a
  typed AST with pure-Python actions.
- [`examples/lisp_interpreter.py`](../examples/lisp_interpreter.py) — a
  larger example driving evaluation from actions.
