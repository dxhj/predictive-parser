"""Serialize precomputed parse tables to JSON.

This avoids recomputing FIRST/FOLLOW/NULLABLE on every program start for
large grammars.  Serialized form is intentionally a plain JSON document so
it can be version-controlled and inspected.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .sets import EPSILON


def dump_tables(parser: Any, path: str | os.PathLike[str]) -> None:
    """Write a parser's grammar + parse table to ``path`` as JSON."""

    payload = to_json(parser)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)


def load_tables(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a serialized tables document."""

    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def to_json(parser: Any) -> dict[str, Any]:
    """Serialize a parser to a JSON-compatible dict."""

    return {
        "version": 1,
        "start": parser.start,
        "terminals": sorted(parser.terminals),
        "nonterminals": sorted(parser.nonterminals),
        "grammar": {
            head: [list(p) for p in prods]
            for head, prods in parser.grammar.items()
        },
        "nullable": {k: v for k, v in parser.null_dict.items()},
        "first": {k: sorted(v) for k, v in parser.first_dict.items()},
        "follow": {k: sorted(v) for k, v in parser.follow_dict.items()},
        "table": [
            {"nt": nt, "t": t, "prod": list(prod)}
            for (nt, t), prod in sorted(parser.table.items())
        ],
    }


def from_json(payload: dict[str, Any]) -> Any:
    """Rebuild a :class:`PredictiveParser` from a JSON payload.

    This rebuilds via the normal constructor (ensures table consistency).
    Offered as a convenience to pair with :func:`dump_tables`.
    """

    from .parser import PredictiveParser

    grammar = {
        head: [
            [sym for sym in prod] if prod else [EPSILON]
            for prod in prods
        ]
        for head, prods in payload["grammar"].items()
    }
    return PredictiveParser(payload["start"], grammar)


__all__ = ["dump_tables", "from_json", "load_tables", "to_json"]
