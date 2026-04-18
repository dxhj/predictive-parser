"""Tests for the ``predictive-parser`` CLI."""

from __future__ import annotations

from predictive_parser.cli import main

_GRAMMAR = r"""
%start Expr
%skip WS = "\s+"
%token NUM = "[0-9]+"
%token PLUS = "\+"

Expr -> NUM (PLUS NUM)* ;
"""


def _write_grammar(tmp_path) -> str:
    p = tmp_path / "g.gr"
    p.write_text(_GRAMMAR)
    return str(p)


class TestCLI:
    def test_check(self, tmp_path, capsys) -> None:
        gp = _write_grammar(tmp_path)
        rc = main(["check", gp])
        out = capsys.readouterr().out
        assert rc == 0
        assert "start: Expr" in out
        assert "parse table" in out

    def test_first(self, tmp_path, capsys) -> None:
        gp = _write_grammar(tmp_path)
        rc = main(["first", gp])
        out = capsys.readouterr().out
        assert rc == 0
        assert "FIRST(Expr)" in out

    def test_follow(self, tmp_path, capsys) -> None:
        gp = _write_grammar(tmp_path)
        rc = main(["follow", gp])
        out = capsys.readouterr().out
        assert rc == 0
        assert "FOLLOW(Expr)" in out

    def test_dump(self, tmp_path) -> None:
        gp = _write_grammar(tmp_path)
        op = tmp_path / "out.json"
        rc = main(["dump", gp, str(op)])
        assert rc == 0
        assert op.exists()

    def test_parse_success(self, tmp_path, capsys) -> None:
        gp = _write_grammar(tmp_path)
        ip = tmp_path / "in.txt"
        ip.write_text("1 + 2 + 3")
        rc = main(["parse", gp, str(ip)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Expr" in out

    def test_parse_failure(self, tmp_path, capsys) -> None:
        gp = _write_grammar(tmp_path)
        ip = tmp_path / "in.txt"
        ip.write_text("+")
        rc = main(["parse", gp, str(ip)])
        err = capsys.readouterr().err
        assert rc != 0
        assert "syntax error" in err
