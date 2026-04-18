"""Tests for the grammar DSL and EBNF desugaring."""

from __future__ import annotations

import pytest

from predictive_parser import ParseError, PredictiveParser, parse_grammar


class TestDSLBasics:
    def test_simple_grammar(self) -> None:
        src = """
        S -> 'a' ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a"])
        assert not p.match(["b"])

    def test_multiple_alternatives(self) -> None:
        src = "S -> 'a' | 'b' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a"])
        assert p.match(["b"])
        assert not p.match(["c"])

    def test_epsilon(self) -> None:
        src = "S -> 'a' | epsilon ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a"])
        assert p.match([])

    def test_unicode_epsilon(self) -> None:
        src = "S -> 'a' | \u03b5 ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match([])

    def test_line_and_block_comments(self) -> None:
        src = """
        // a line comment
        # another line comment
        /* block
           comment */
        S -> 'a' ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a"])

    def test_multi_char_terminal(self) -> None:
        src = 'S -> "hello" ;'
        p = PredictiveParser.from_grammar(src)
        assert p.match(["hello"])

    def test_escape_sequences_in_terminal(self) -> None:
        src = r"""S -> '\n' ;"""
        p = PredictiveParser.from_grammar(src)
        assert p.match(["\n"])

    def test_start_directive(self) -> None:
        src = """
        %start Main
        Main -> 'x' Other ;
        Other -> 'y' ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.start == "Main"
        assert p.match(["x", "y"])

    def test_default_start_is_first_rule(self) -> None:
        src = """
        First -> Second 'a' ;
        Second -> 'b' ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.start == "First"

    def test_colon_arrow_supported(self) -> None:
        src = "S : 'a' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a"])

    def test_bnf_arrow_supported(self) -> None:
        src = "S ::= 'a' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a"])

    def test_error_on_unknown_directive(self) -> None:
        with pytest.raises(ParseError):
            PredictiveParser.from_grammar("%unknown X ;")

    def test_error_on_bad_character(self) -> None:
        with pytest.raises(ParseError):
            PredictiveParser.from_grammar("S -> @ ;")


class TestEBNFDesugar:
    def test_optional(self) -> None:
        src = "S -> 'a' 'b'? 'c' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a", "b", "c"])
        assert p.match(["a", "c"])
        assert not p.match(["a", "b"])

    def test_star(self) -> None:
        src = "S -> 'a'* 'b' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["b"])
        assert p.match(["a", "b"])
        assert p.match(["a", "a", "a", "b"])
        assert not p.match(["a"])

    def test_plus(self) -> None:
        src = "S -> 'a'+ 'b' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a", "b"])
        assert p.match(["a", "a", "b"])
        assert not p.match(["b"])

    def test_group(self) -> None:
        src = "S -> ('a' 'b') 'c' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a", "b", "c"])

    def test_group_with_alternatives(self) -> None:
        src = "S -> ('a' | 'b') 'c' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a", "c"])
        assert p.match(["b", "c"])
        assert not p.match(["c"])

    def test_comma_separated_list(self) -> None:
        src = "List -> 'x' (',' 'x')* ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["x"])
        assert p.match(["x", ",", "x"])
        assert p.match(["x", ",", "x", ",", "x"])
        assert not p.match([])

    def test_optional_group(self) -> None:
        src = "S -> 'a' ('b' 'c')? 'd' ;"
        p = PredictiveParser.from_grammar(src)
        assert p.match(["a", "d"])
        assert p.match(["a", "b", "c", "d"])


class TestDSLWithTokens:
    def test_token_and_skip_directives(self) -> None:
        src = r"""
        %skip WS = "\s+"
        %token NUM = "[0-9]+"
        %token PLUS = "\+"
        Expr -> NUM (PLUS NUM)* ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.lexer is not None
        tree = p.parse_text("1 + 2 + 3")
        assert tree.symbol == "Expr"

    def test_parse_text_without_lexer_raises(self) -> None:
        p = PredictiveParser("S", {"S": [["a"]]})
        with pytest.raises(ValueError, match="Lexer"):
            p.parse_text("a")


class TestDSLErrors:
    def test_unterminated_action(self) -> None:
        with pytest.raises(ParseError, match="action"):
            parse_grammar("S -> 'a' { $$ = 1 ;")

    def test_missing_semicolon(self) -> None:
        with pytest.raises(ParseError):
            parse_grammar("S -> 'a' T -> 'b' ;")
