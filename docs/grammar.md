# Grammar DSL Reference

Grammar files are UTF-8 text.  Whitespace is insignificant except as a
token separator.

## Rules

```text
Head -> Body [ { action } ] ( '|' Body [ { action } ] )* ';'
```

Either `->`, `::=`, or `:` may be used as the rule arrow.
Every rule must end with `;`.

Each body is a sequence of atoms:

- **Nonterminal reference** — an identifier like `Expr`.  Identifiers
  may contain Unicode letters, digits, `_`, and `'`.
- **Terminal literal** — a single- or double-quoted string like `"+"`
  or `'if'`.  Escape sequences `\n \t \r \0 \\ \' \"` are decoded;
  anything else (including `\s`, `\+`, `\d`) passes through unchanged so
  that regex patterns in `%token` declarations survive.
- **`epsilon`** / **`ε`** / **`EPSILON`** — empty production.

### EBNF sugar

- `X?`   — optional (0 or 1 occurrence)
- `X*`   — zero or more
- `X+`   — one or more
- `(X Y | Z)` — parenthesized group, may contain alternatives

Sugar is desugared into fresh helper nonterminals named `<head>__N`.
You can see the final grammar by calling `parser.grammar` or running
`predictive-parser check`.

## Directives

- `%start Name` — declare the start nonterminal.  Optional; defaults to
  the first rule in the file.
- `%token NAME = "regex"` — declare a terminal and its lexer pattern.
  The parser auto-constructs a `Lexer` from all declared tokens.
- `%skip NAME = "regex"` — like `%token` but matched text is discarded
  (whitespace, comments).

All three directives may optionally end with `;`.

## Semantic actions

An action is a Python expression block in `{ ... }`:

```text
Expr -> Term '+' Expr  { $$ = $1 + $3 } ;
```

- `$$` — the semantic value this production produces
- `$1`, `$2`, ... — values of the children in left-to-right order
- Children that are terminals evaluate to the token object itself;
  access `.value` or `.type` as needed.

The block is compiled to a Python function once at load time.

## Comments

- `// line comment`
- `# line comment`
- `/* block comment */`

## Complete example

```text
%start Json
%skip  WS       = "\s+"
%token STRING   = "\"(?:\\.|[^\"\\])*\""
%token NUMBER   = "-?[0-9]+(?:\.[0-9]+)?"
%token TRUE     = "true"
%token FALSE    = "false"
%token NULL     = "null"
%token LBRACE   = "\{"
%token RBRACE   = "\}"
%token LBRACK   = "\["
%token RBRACK   = "\]"
%token COMMA    = ","
%token COLON    = ":"

Json   -> Value ;
Value  -> Object | Array | STRING | NUMBER | TRUE | FALSE | NULL ;
Object -> LBRACE Members? RBRACE ;
Members -> Member (COMMA Member)* ;
Member -> STRING COLON Value ;
Array  -> LBRACK Elements? RBRACK ;
Elements -> Value (COMMA Value)* ;
```
