"""Build a custom AST from the calculator grammar.

Same grammar as ``calculator.py`` — but instead of computing the numeric
result inline with ``{ ... }`` actions, we keep the grammar clean and
register Python actions that construct nodes from our own AST module.
Afterwards we walk the tree with a simple evaluator and a pretty-printer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from predictive_parser import PredictiveParser


Expr = Union["Num", "BinOp"]


@dataclass(frozen=True)
class Num:
    value: int


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Expr
    right: Expr


GRAMMAR = r"""
%start Expr
%skip  WS    = "\s+"
%token NUM   = "[0-9]+"
%token PLUS  = "\+"
%token STAR  = "\*"
%token LP    = "\("
%token RP    = "\)"

Expr   -> Term Exprp ;
Exprp  -> PLUS Term Exprp
       |  epsilon ;
Term   -> Factor Termp ;
Termp  -> STAR Factor Termp
       |  epsilon ;
Factor -> LP Expr RP
       |  NUM ;
"""


def build_parser() -> PredictiveParser:
    parser = PredictiveParser.from_grammar(GRAMMAR)

    # The "primed" nonterminals Exprp / Termp are right-recursive tails
    # introduced to remove left recursion.  We have them return a flat
    # list of (operator, operand) pairs, then fold them left-associatively
    # at the Expr / Term level so that ``1 + 2 + 3`` becomes
    # ``BinOp('+', BinOp('+', 1, 2), 3)`` rather than a right-leaning tree.

    @parser.action("Expr -> Term Exprp")
    def _expr(values):
        left, tail = values
        for op, right in tail:
            left = BinOp(op, left, right)
        return left

    @parser.action("Exprp -> PLUS Term Exprp")
    def _exprp_plus(values):
        _plus_tok, term, rest = values
        return [("+", term), *rest]

    @parser.action("Exprp -> epsilon")
    def _exprp_empty(_values):
        return []

    @parser.action("Term -> Factor Termp")
    def _term(values):
        left, tail = values
        for op, right in tail:
            left = BinOp(op, left, right)
        return left

    @parser.action("Termp -> STAR Factor Termp")
    def _termp_star(values):
        _star_tok, factor, rest = values
        return [("*", factor), *rest]

    @parser.action("Termp -> epsilon")
    def _termp_empty(_values):
        return []

    @parser.action("Factor -> LP Expr RP")
    def _factor_parens(values):
        return values[1]

    @parser.action("Factor -> NUM")
    def _factor_num(values):
        tok = values[0]
        return Num(int(tok.value))

    return parser


def evaluate(node: Expr) -> int:
    if isinstance(node, Num):
        return node.value
    left = evaluate(node.left)
    right = evaluate(node.right)
    if node.op == "+":
        return left + right
    if node.op == "*":
        return left * right
    raise ValueError(f"unknown operator: {node.op!r}")


def pretty(node: Expr) -> str:
    if isinstance(node, Num):
        return str(node.value)
    return f"({pretty(node.left)} {node.op} {pretty(node.right)})"


def main() -> None:
    parser = build_parser()
    sources = ["1 + 2", "2 * 3 + 4", "(1 + 2) * 3", "10 + 20 * 3", "1 + 2 + 3"]
    for src in sources:
        ast = parser.parse_text(src)
        print(f"{src:<16} -> {pretty(ast):<24} = {evaluate(ast)}")


if __name__ == "__main__":
    main()
