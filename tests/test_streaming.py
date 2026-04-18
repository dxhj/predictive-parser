"""Tests that the parser accepts arbitrary token iterators, not just lists."""

from __future__ import annotations

from predictive_parser import EPSILON, PredictiveParser, SimpleToken


def _expr() -> PredictiveParser:
    return PredictiveParser(
        "E",
        {
            "E": [["T", "Ep"]],
            "Ep": [["+", "T", "Ep"], [EPSILON]],
            "T": [["id"]],
        },
    )


class TestStreamingInput:
    def test_accepts_generator(self) -> None:
        p = _expr()

        def gen():
            yield "id"
            yield "+"
            yield "id"

        assert p.match(gen())

    def test_accepts_iterator(self) -> None:
        p = _expr()
        tokens = iter(["id", "+", "id"])
        assert p.match(tokens)

    def test_accepts_lazy_token_stream(self) -> None:
        p = _expr()
        count = [0]

        def gen():
            for t in ["id", "+", "id"]:
                count[0] += 1
                yield SimpleToken(type=t, value=t)

        assert p.match(gen())
        assert count[0] == 3

    def test_accepts_empty_iterator(self) -> None:
        p = _expr()
        assert not p.match(iter([]))

    def test_parse_returns_tree_from_iterator(self) -> None:
        p = _expr()
        tree = p.parse(iter(["id"]))
        assert tree.symbol == "E"

    def test_mixed_stream(self) -> None:
        p = _expr()
        stream = iter(["id", SimpleToken(type="+"), "id"])
        assert p.match(stream)
