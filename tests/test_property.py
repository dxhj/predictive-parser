"""Property-based tests using Hypothesis."""

from __future__ import annotations

import pytest

pytest.importorskip("hypothesis")

from hypothesis import given
from hypothesis import strategies as st

from predictive_parser import EPSILON, PredictiveParser


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


def _parens_parser() -> PredictiveParser:
    # S -> ( S ) S | ε  — classic balanced-parens LL(1) grammar.
    return PredictiveParser(
        "S",
        {
            "S": [["(", "S", ")", "S"], [EPSILON]],
        },
    )


_EXPR_PARSER = _expr_parser()
_PARENS_PARSER = _parens_parser()


ATOMS = [
    ["id"],
    ["(", "id", ")"],
    ["(", "id", "+", "id", ")"],
    ["(", "id", "*", "id", ")"],
]


@st.composite
def expr_tokens(draw):
    parts = list(draw(st.sampled_from(ATOMS)))
    n = draw(st.integers(min_value=0, max_value=6))
    for _ in range(n):
        op = draw(st.sampled_from(["+", "*"]))
        parts.append(op)
        parts.extend(draw(st.sampled_from(ATOMS)))
    return parts


class TestValidExpressions:
    @given(expr_tokens())
    def test_parser_accepts(self, tokens: list[str]) -> None:
        assert _EXPR_PARSER.match(tokens), tokens

    @given(expr_tokens())
    def test_match_is_idempotent(self, tokens: list[str]) -> None:
        first = _EXPR_PARSER.match(tokens)
        second = _EXPR_PARSER.match(tokens)
        assert first == second

    @given(expr_tokens())
    def test_parse_produces_tree(self, tokens: list[str]) -> None:
        tree = _EXPR_PARSER.parse(tokens)
        assert tree.symbol == "E"
        leaves = [t.type for t in tree.terminals()]
        assert leaves == tokens


def _balanced(depth_max: int = 4):
    return st.recursive(
        st.just(""),
        lambda inner: st.lists(inner, max_size=3).map(
            lambda xs: "(" + "".join(xs) + ")"
        ),
        max_leaves=depth_max,
    )


@st.composite
def balanced_seq(draw):
    parts = draw(st.lists(_balanced(), max_size=3))
    s = "".join(parts)
    return list(s)


class TestBalancedParens:
    @given(balanced_seq())
    def test_balanced_accepted(self, toks: list[str]) -> None:
        assert _PARENS_PARSER.match(toks), toks
