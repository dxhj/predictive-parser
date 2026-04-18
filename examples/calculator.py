"""Full calculator example using the DSL, a built-in lexer, and inline actions."""

from __future__ import annotations

from predictive_parser import PredictiveParser

GRAMMAR = r"""
%start Expr
%skip  WS    = "\s+"
%token NUM   = "[0-9]+"
%token PLUS  = "\+"
%token STAR  = "\*"
%token LP    = "\("
%token RP    = "\)"

Expr   -> Term Exprp        { $$ = $1 + $2 } ;
Exprp  -> PLUS Term Exprp   { $$ = $2 + $3 }
       |  epsilon           { $$ = 0 } ;
Term   -> Factor Termp      { $$ = $1 * ($2 if $2 != 0 else 1) } ;
Termp  -> STAR Factor Termp { $$ = $2 * ($3 if $3 != 0 else 1) }
       |  epsilon           { $$ = 0 } ;
Factor -> LP Expr RP        { $$ = $2 }
       |  NUM               { $$ = int($1.value) } ;
"""


def main() -> None:
    calc = PredictiveParser.from_grammar(GRAMMAR)
    for src in ["1 + 2", "2 * 3 + 4", "(1 + 2) * 3", "10 + 20 * 3"]:
        print(f"{src:<20} = {calc.parse_text(src)}")


if __name__ == "__main__":
    main()
