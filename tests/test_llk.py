"""Tests for LL(k) FIRST_k machinery."""

from __future__ import annotations

import pytest

from predictive_parser import build_llk_table
from predictive_parser.sets import compute_first_k


class TestFirstK:
    def test_first_1_matches_first(self) -> None:
        grammar = {"S": [["a"], ["b", "c"]]}
        fk = compute_first_k(grammar, ["a", "b", "c"], k=1)
        assert fk["S"] == {("a",), ("b",)}

    def test_first_2(self) -> None:
        grammar = {"S": [["a", "b"], ["a", "c"]]}
        fk = compute_first_k(grammar, ["a", "b", "c"], k=2)
        assert fk["S"] == {("a", "b"), ("a", "c")}

    def test_k_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            compute_first_k({"S": [["a"]]}, ["a"], k=0)


class TestLLkTable:
    def test_ll2_resolves_ll1_conflict(self) -> None:
        grammar = {"S": [["a", "b"], ["a", "c"]]}
        table = build_llk_table(grammar, "S", ["a", "b", "c"], k=2)
        assert table[("S", ("a", "b"))] == ["a", "b"]
        assert table[("S", ("a", "c"))] == ["a", "c"]
