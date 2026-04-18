"""Tests for the regex-based Lexer and token protocol."""

from __future__ import annotations

import pytest

from predictive_parser import (
    Lexer,
    LexerError,
    SimpleToken,
    Token,
    TokenLike,
    TokenRule,
    from_ply_lexer,
    get_location,
)


@pytest.fixture
def math_lexer() -> Lexer:
    return Lexer(
        [
            TokenRule(name="_WS", pattern=r"\s+", skip=True),
            TokenRule(name="NUM", pattern=r"\d+"),
            TokenRule(name="PLUS", pattern=r"\+"),
            TokenRule(name="STAR", pattern=r"\*"),
            TokenRule(name="LP", pattern=r"\("),
            TokenRule(name="RP", pattern=r"\)"),
        ]
    )


class TestLexerBasics:
    def test_simple_tokenize(self, math_lexer: Lexer) -> None:
        toks = math_lexer.tokenize("1 + 2")
        assert [t.type for t in toks] == ["NUM", "PLUS", "NUM"]
        assert [t.value for t in toks] == ["1", "+", "2"]

    def test_skip_rule(self, math_lexer: Lexer) -> None:
        toks = math_lexer.tokenize("  1+2  ")
        assert [t.type for t in toks] == ["NUM", "PLUS", "NUM"]

    def test_line_column_tracking(self, math_lexer: Lexer) -> None:
        toks = math_lexer.tokenize("1 +\n2")
        assert toks[0].line == 1 and toks[0].column == 1
        assert toks[1].line == 1 and toks[1].column == 3
        assert toks[2].line == 2 and toks[2].column == 1

    def test_offset_tracking(self, math_lexer: Lexer) -> None:
        toks = math_lexer.tokenize("1+2")
        assert toks[0].offset == 0
        assert toks[1].offset == 1
        assert toks[2].offset == 2

    def test_unknown_character_raises(self, math_lexer: Lexer) -> None:
        with pytest.raises(LexerError) as ei:
            math_lexer.tokenize("1 @ 2")
        assert "@" in str(ei.value)

    def test_keyword_disambiguation(self) -> None:
        lex = Lexer(
            [
                TokenRule(name="_WS", pattern=r"\s+", skip=True),
                TokenRule(
                    name="IDENT",
                    pattern=r"[A-Za-z_][A-Za-z0-9_]*",
                    keywords={"if": "IF", "else": "ELSE"},
                ),
            ]
        )
        toks = lex.tokenize("if foo else")
        assert [t.type for t in toks] == ["IF", "IDENT", "ELSE"]

    def test_lazy_lex(self, math_lexer: Lexer) -> None:
        it = math_lexer.lex("1 + 2")
        first = next(it)
        assert first.type == "NUM"
        rest = list(it)
        assert [t.type for t in rest] == ["PLUS", "NUM"]

    def test_empty_rules_rejected(self) -> None:
        with pytest.raises(ValueError):
            Lexer([])


class TestTokenProtocol:
    def test_simple_token_is_token_like(self) -> None:
        assert isinstance(SimpleToken(type="x"), TokenLike)

    def test_lexer_token_is_token_like(self) -> None:
        tok = Token(type="x", value="x")
        assert isinstance(tok, TokenLike)

    def test_get_location_from_lexer_token(self) -> None:
        tok = Token(type="x", value="x", line=3, column=4, offset=5)
        loc = get_location(tok)
        assert loc.line == 3
        assert loc.column == 4
        assert loc.offset == 5

    def test_get_location_from_ply_style(self) -> None:
        class PLY:
            def __init__(self) -> None:
                self.type = "X"
                self.lineno = 7
                self.lexpos = 10

        loc = get_location(PLY())
        assert loc.line == 7
        assert loc.offset == 10

    def test_get_location_none(self) -> None:
        loc = get_location(None)
        assert loc.line is None


class TestPLYAdapter:
    def test_from_ply_lexer(self) -> None:
        class FakePLY:
            def __init__(self, tokens: list[SimpleToken]) -> None:
                self.tokens = list(tokens)

            def token(self) -> SimpleToken | None:
                return self.tokens.pop(0) if self.tokens else None

        source = [SimpleToken(type="a"), SimpleToken(type="b")]
        it = from_ply_lexer(FakePLY(source))
        assert [t.type for t in it] == ["a", "b"]
