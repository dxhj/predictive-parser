"""Command-line interface for predictive-parser.

Usage::

    predictive-parser check grammar.gr         # validate + print table
    predictive-parser first grammar.gr         # print FIRST sets
    predictive-parser follow grammar.gr        # print FOLLOW sets
    predictive-parser parse grammar.gr -       # read input from stdin and parse
    predictive-parser dump grammar.gr out.json # serialize tables
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import ParseError
from .parser import PredictiveParser
from .serialization import dump_tables


def _load(path: str) -> PredictiveParser:
    return PredictiveParser.from_grammar_file(path)


def _cmd_check(args: argparse.Namespace) -> int:
    parser = _load(args.grammar)
    print(f"start: {parser.start}")
    print(f"terminals: {sorted(parser.terminals)}")
    print(f"nonterminals: {sorted(parser.nonterminals)}")
    print("parse table:")
    for (nt, t), prod in sorted(parser.table.items()):
        body = " ".join(prod) if prod != [""] else "\u03b5"
        print(f"  ({nt}, {t}) -> {body}")
    return 0


def _cmd_first(args: argparse.Namespace) -> int:
    parser = _load(args.grammar)
    for k in sorted(parser.first_dict.keys()):
        print(f"FIRST({k}) = {sorted(parser.first_dict[k])}")
    return 0


def _cmd_follow(args: argparse.Namespace) -> int:
    parser = _load(args.grammar)
    for k in sorted(parser.follow_dict.keys()):
        print(f"FOLLOW({k}) = {sorted(parser.follow_dict[k])}")
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    parser = _load(args.grammar)
    text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(
        encoding="utf-8"
    )
    try:
        if parser.lexer is not None:
            tree = parser.parse_text(text)
        else:
            tokens = text.split()
            tree = parser.parse(tokens)
    except ParseError as exc:
        print(f"syntax error: {exc}", file=sys.stderr)
        return 1
    print(tree.pretty() if hasattr(tree, "pretty") else tree)
    return 0


def _cmd_dump(args: argparse.Namespace) -> int:
    parser = _load(args.grammar)
    dump_tables(parser, args.output)
    print(f"wrote {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="predictive-parser",
        description="LL(1) predictive parser — inspection and parsing CLI",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="validate grammar and print parse table")
    pc.add_argument("grammar")
    pc.set_defaults(func=_cmd_check)

    pf = sub.add_parser("first", help="print FIRST sets")
    pf.add_argument("grammar")
    pf.set_defaults(func=_cmd_first)

    pfl = sub.add_parser("follow", help="print FOLLOW sets")
    pfl.add_argument("grammar")
    pfl.set_defaults(func=_cmd_follow)

    pp = sub.add_parser("parse", help="parse an input against a grammar")
    pp.add_argument("grammar")
    pp.add_argument("input", help="path to input, or '-' for stdin")
    pp.set_defaults(func=_cmd_parse)

    pd = sub.add_parser("dump", help="dump precomputed tables as JSON")
    pd.add_argument("grammar")
    pd.add_argument("output")
    pd.set_defaults(func=_cmd_dump)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
