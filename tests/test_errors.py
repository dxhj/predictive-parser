"""Tests for error reporting, source locations, and listeners."""

from __future__ import annotations

import pytest

from predictive_parser import (
    EPSILON,
    DefaultErrorListener,
    ParseError,
    PredictiveParser,
    SimpleToken,
    SourceLocation,
)


def _p() -> PredictiveParser:
    return PredictiveParser(
        "E",
        {
            "E": [["T", "Ep"]],
            "Ep": [["+", "T", "Ep"], [EPSILON]],
            "T": [["id"]],
        },
    )


class TestRaisingListener:
    def test_parse_raises_on_error(self) -> None:
        p = _p()
        with pytest.raises(ParseError) as ei:
            p.parse(["+"])
        assert "id" in ei.value.expected or "+" in ei.value.message

    def test_parse_error_carries_location(self) -> None:
        p = _p()
        tokens = [
            SimpleToken(type="+", value="+", line=3, column=7, offset=10),
        ]
        with pytest.raises(ParseError) as ei:
            p.parse(tokens)
        assert ei.value.location.line == 3
        assert ei.value.location.column == 7

    def test_unexpected_trailing_token(self) -> None:
        p = _p()
        with pytest.raises(ParseError):
            p.parse(["id", "id"])


class TestDefaultListener:
    def test_collects_errors_without_raising(self) -> None:
        listener = DefaultErrorListener()
        p = PredictiveParser(
            "E",
            {
                "E": [["T", "Ep"]],
                "Ep": [["+", "T", "Ep"], [EPSILON]],
                "T": [["id"]],
            },
            error_listener=listener,
        )
        out = p.detailed_match(["+"])
        assert not out.success
        assert len(listener.errors) == 1
        assert listener.errors[0].got == "+"


class TestSourceLocation:
    def test_str_with_line_column(self) -> None:
        loc = SourceLocation(line=2, column=4)
        assert "line 2" in str(loc)
        assert "column 4" in str(loc)

    def test_str_unknown(self) -> None:
        assert str(SourceLocation()) == "<unknown>"

    def test_str_offset_only(self) -> None:
        loc = SourceLocation(offset=5)
        assert "offset 5" in str(loc)


class TestParseErrorRepr:
    def test_parse_error_str(self) -> None:
        err = ParseError(
            message="bad",
            location=SourceLocation(line=1, column=2),
            expected=frozenset({"a"}),
            got="b",
        )
        assert str(err) == "bad"


class TestExpectedSetIndexed:
    def test_expected_set_matches_table(self) -> None:
        p = _p()
        result = p.detailed_match(["+"])
        # Expected should be FIRST of productions for E reachable at start.
        assert "id" in result.expected
