"""Tests for parse trees, visitors, and listeners."""

from __future__ import annotations

from predictive_parser import (
    EPSILON,
    ParseTree,
    ParseTreeListener,
    ParseTreeVisitor,
    PredictiveParser,
    SimpleToken,
)


def _expr_parser() -> PredictiveParser:
    return PredictiveParser(
        "E",
        {
            "E": [["T", "Ep"]],
            "Ep": [["+", "T", "Ep"], [EPSILON]],
            "T": [["F", "Tp"]],
            "Tp": [["*", "F", "Tp"], [EPSILON]],
            "F": [["(", "E", ")"], ["id"]],
        },
    )


class TestParseTreeConstruction:
    def test_parse_returns_tree(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id"])
        assert isinstance(tree, ParseTree)
        assert tree.symbol == "E"

    def test_tree_children_for_epsilon(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id"])
        # E -> T Ep, Ep -> ε: should still exist as a child with 0 children.
        ep = [c for c in tree.children if isinstance(c, ParseTree) and c.symbol == "Ep"][0]
        assert ep.children == []
        assert ep.production == ()

    def test_tree_terminals_are_tokens(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id"])
        terminals = list(tree.terminals())
        assert len(terminals) == 1
        assert terminals[0].type == "id"

    def test_tree_walk_preorder(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id", "+", "id"])
        symbols = [
            n.symbol if isinstance(n, ParseTree) else n.type
            for n in tree.walk()
        ]
        assert symbols[0] == "E"
        assert "T" in symbols
        assert "Ep" in symbols

    def test_pretty_includes_symbols(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id"])
        dump = tree.pretty()
        assert "E" in dump
        assert "id" in dump


class TestVisitor:
    def test_default_visitor_walks_all(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id", "+", "id"])

        class V(ParseTreeVisitor):
            def __init__(self) -> None:
                self.visited: list[str] = []

            def visit_E(self, node: ParseTree):
                self.visited.append(node.symbol)
                return self.visit_children(node)

            def visit_F(self, node: ParseTree):
                self.visited.append(node.symbol)
                return self.visit_children(node)

        v = V()
        v.visit(tree)
        assert "E" in v.visited
        assert v.visited.count("F") == 2


class TestListener:
    def test_enter_exit_calls(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id"])
        events: list[tuple[str, str]] = []

        class L(ParseTreeListener):
            def enter_every_rule(self, node: ParseTree) -> None:
                events.append(("enter", node.symbol))

            def exit_every_rule(self, node: ParseTree) -> None:
                events.append(("exit", node.symbol))

            def visit_terminal(self, token) -> None:  # type: ignore[override]
                events.append(("term", token.type))

        L().walk(tree)
        assert ("enter", "E") in events
        assert ("term", "id") in events
        assert events[0] == ("enter", "E")
        assert events[-1] == ("exit", "E")

    def test_specific_enter_exit(self) -> None:
        p = _expr_parser()
        tree = p.parse(["id"])
        calls: list[str] = []

        class L(ParseTreeListener):
            def enter_F(self, node: ParseTree) -> None:
                calls.append("enter_F")

            def exit_F(self, node: ParseTree) -> None:
                calls.append("exit_F")

        L().walk(tree)
        assert calls == ["enter_F", "exit_F"]


class TestTreeLocation:
    def test_location_from_first_token(self) -> None:
        p = _expr_parser()
        tokens = [
            SimpleToken(type="id", value="x", line=1, column=1, offset=0),
        ]
        tree = p.parse(tokens)
        assert tree.location.line == 1
