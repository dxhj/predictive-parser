"""Tests for semantic actions via value stack."""

from __future__ import annotations

import pytest

from predictive_parser import EPSILON, ActionError, PredictiveParser


def _calc_parser() -> PredictiveParser:
    return PredictiveParser(
        "E",
        {
            "E": [["T", "Ep"]],
            "Ep": [["+", "T", "Ep"], [EPSILON]],
            "T": [["F", "Tp"]],
            "Tp": [["*", "F", "Tp"], [EPSILON]],
            "F": [["(", "E", ")"], ["num"]],
        },
    )


class TestDecoratorActions:
    def test_simple_addition(self) -> None:
        p = _calc_parser()

        @p.action("F -> 'num'")
        def f_num(v):
            return int(v[0].value or "0")

        @p.action("F -> '(' E ')'")
        def f_paren(v):
            return v[1]

        @p.action("Tp -> '*' F Tp")
        def tp_mul(v):
            return ("mul", v[1], v[2])

        @p.action("Tp ->")
        def tp_eps(v):
            return None

        @p.action("T -> F Tp")
        def t_prod(v):
            left = v[0]
            rest = v[1]
            while rest is not None and rest[0] == "mul":
                left = left * rest[1]
                rest = rest[2]
            return left

        @p.action("Ep -> '+' T Ep")
        def ep_plus(v):
            return ("plus", v[1], v[2])

        @p.action("Ep ->")
        def ep_eps(v):
            return None

        @p.action("E -> T Ep")
        def e_prod(v):
            left = v[0]
            rest = v[1]
            while rest is not None and rest[0] == "plus":
                left = left + rest[1]
                rest = rest[2]
            return left

        from predictive_parser import SimpleToken

        tokens = [
            SimpleToken(type="num", value="2"),
            SimpleToken(type="+", value="+"),
            SimpleToken(type="num", value="3"),
            SimpleToken(type="*", value="*"),
            SimpleToken(type="num", value="4"),
        ]
        assert p.parse(tokens) == 14


class TestProgrammaticActions:
    def test_set_action_directly(self) -> None:
        p = PredictiveParser("S", {"S": [["x"]]})
        p.set_action("S", ("x",), lambda v: v[0].value)
        from predictive_parser import SimpleToken

        assert p.parse([SimpleToken(type="x", value="hi")]) == "hi"


class TestActionError:
    def test_action_exception_wrapped(self) -> None:
        p = PredictiveParser("S", {"S": [["x"]]})

        @p.action("S -> 'x'")
        def bad(v):
            raise RuntimeError("boom")

        with pytest.raises(ActionError) as ei:
            p.parse(["x"])
        assert "boom" in str(ei.value)
        assert "S" in str(ei.value)


class TestDSLInlineActions:
    def test_bison_style_inline(self) -> None:
        src = r"""
        %start E
        E  -> T Ep           { $$ = $1 + $2 } ;
        Ep -> "+" T Ep       { $$ = $2 + $3 }
            | epsilon        { $$ = 0 } ;
        T  -> "num"          { $$ = 1 } ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.parse(["num", "+", "num", "+", "num"]) == 3
