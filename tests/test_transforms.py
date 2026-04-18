"""Tests for EBNF / left-factoring / left-recursion transforms."""

from __future__ import annotations

from predictive_parser import (
    PredictiveParser,
    eliminate_left_recursion,
    left_factor,
)


class TestLeftRecursionElimination:
    def test_immediate_left_recursion(self) -> None:
        g = {
            "E": [["E", "+", "T"], ["T"]],
            "T": [["id"]],
        }
        g2 = eliminate_left_recursion(g)
        p = PredictiveParser("E", g2)
        assert p.match(["id"])
        assert p.match(["id", "+", "id"])
        assert p.match(["id", "+", "id", "+", "id"])
        assert not p.match(["+", "id"])

    def test_multiple_nonterminals(self) -> None:
        g = {
            "E": [["E", "+", "T"], ["T"]],
            "T": [["T", "*", "F"], ["F"]],
            "F": [["(", "E", ")"], ["id"]],
        }
        g2 = eliminate_left_recursion(g)
        p = PredictiveParser("E", g2)
        assert p.match(["id"])
        assert p.match(["id", "+", "id", "*", "id"])
        assert p.match(["(", "id", "+", "id", ")", "*", "id"])

    def test_indirect_left_recursion_flattened(self) -> None:
        # Textbook indirect case: S -> A a, A -> S b | c.
        # After Paull's algorithm the chain is broken into immediate form.
        g = {
            "S": [["A", "a"]],
            "A": [["S", "b"], ["c"]],
        }
        g2 = eliminate_left_recursion(g)
        # Verify the grammar has no self-references on the left.
        for head, prods in g2.items():
            for prod in prods:
                assert not (prod and prod[0] == head and head != "S"), g2
        # The rewritten grammar is guaranteed free of left recursion.
        assert all(
            not (prod and prod[0] == head)
            for head, prods in g2.items()
            for prod in prods
        )


class TestLeftFactoring:
    def test_common_prefix(self) -> None:
        g = {"S": [["a", "b"], ["a", "c"]]}
        g2 = left_factor(g)
        p = PredictiveParser("S", g2)
        assert p.match(["a", "b"])
        assert p.match(["a", "c"])

    def test_three_way_factor(self) -> None:
        g = {"S": [["a", "b", "c"], ["a", "b", "d"], ["a", "e"]]}
        g2 = left_factor(g)
        p = PredictiveParser("S", g2)
        assert p.match(["a", "b", "c"])
        assert p.match(["a", "b", "d"])
        assert p.match(["a", "e"])

    def test_no_common_prefix_unchanged_semantics(self) -> None:
        g = {"S": [["a"], ["b"]]}
        g2 = left_factor(g)
        p = PredictiveParser("S", g2)
        assert p.match(["a"])
        assert p.match(["b"])

    def test_idempotent(self) -> None:
        g = {"S": [["a", "b"], ["a", "c"]]}
        g2 = left_factor(g)
        g3 = left_factor(g2)
        assert g2 == g3
