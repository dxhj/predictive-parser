"""Build a parse tree and walk it with a visitor."""

from __future__ import annotations

from predictive_parser import EPSILON, ParseTreeVisitor, PredictiveParser

parser = PredictiveParser(
    "E",
    {
        "E":  [["T", "Ep"]],
        "Ep": [["+", "T", "Ep"], [EPSILON]],
        "T":  [["F", "Tp"]],
        "Tp": [["*", "F", "Tp"], [EPSILON]],
        "F":  [["(", "E", ")"], ["id"]],
    },
)


tree = parser.parse(["id", "+", "id", "*", "id"])
print(tree.pretty())
print()


class TerminalCounter(ParseTreeVisitor):
    def __init__(self) -> None:
        self.count = 0

    def visit_terminal(self, token):
        self.count += 1
        return token


v = TerminalCounter()
v.visit(tree)
print(f"tokens in tree: {v.count}")
