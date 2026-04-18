"""Tests for parse-table JSON serialization."""

from __future__ import annotations

import json

from predictive_parser import (
    EPSILON,
    PredictiveParser,
    dump_tables,
    from_json,
    load_tables,
    to_json,
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


class TestJSONRoundtrip:
    def test_to_json_contains_sections(self) -> None:
        p = _p()
        data = to_json(p)
        assert data["version"] == 1
        assert data["start"] == "E"
        assert "table" in data
        assert "first" in data
        assert "follow" in data
        assert "nullable" in data

    def test_from_json_reconstructs_parser(self) -> None:
        p = _p()
        data = to_json(p)
        p2 = from_json(data)
        assert p2.match(["id", "+", "id"])
        assert not p2.match(["+"])

    def test_dump_and_load(self, tmp_path) -> None:
        p = _p()
        out = tmp_path / "tables.json"
        dump_tables(p, out)
        loaded = load_tables(out)
        assert loaded["start"] == "E"
        p2 = from_json(loaded)
        assert p2.match(["id"])

    def test_dump_is_valid_json(self, tmp_path) -> None:
        p = _p()
        out = tmp_path / "t.json"
        dump_tables(p, out)
        json.loads(out.read_text())
