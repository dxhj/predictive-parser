from dataclasses import dataclass

import pytest

from predictive import EPSILON, MatchResult, PredictiveParser, SimpleToken, TokenLike


def _expr_grammar():
    """Classic LL(1) expression grammar.
    E  → T Ep
    Ep → + T Ep | ε
    T  → F Tp
    Tp → * F Tp | ε
    F  → ( E ) | id
    """
    return "E", {
        "E":  [["T", "Ep"]],
        "Ep": [["+", "T", "Ep"], [EPSILON]],
        "T":  [["F", "Tp"]],
        "Tp": [["*", "F", "Tp"], [EPSILON]],
        "F":  [["(", "E", ")"], ["id"]],
    }


def _nullable_prefix_grammar():
    """S → A B   where A is nullable but B is not.
    A → a | ε
    B → b
    """
    return "S", {
        "S": [["A", "B"]],
        "A": [["a"], [EPSILON]],
        "B": [["b"]],
    }


def _all_nullable_grammar():
    """S → A B   where both A and B are nullable.
    A → a | ε
    B → b | ε
    """
    return "S", {
        "S": [["A", "B"]],
        "A": [["a"], [EPSILON]],
        "B": [["b"], [EPSILON]],
    }


def _chained_nullable_grammar():
    """S → A B C   where A and B are nullable.
    A → a | ε
    B → b | ε
    C → c
    Tests that FIRST propagates through multiple nullable symbols.
    """
    return "S", {
        "S": [["A", "B", "C"]],
        "A": [["a"], [EPSILON]],
        "B": [["b"], [EPSILON]],
        "C": [["c"]],
    }


def _single_terminal_grammar():
    """S → x"""
    return "S", {
        "S": [["x"]],
    }


def _ambiguous_grammar():
    """Not LL(1): S → a | a b   (FIRST conflict on 'a')."""
    return "S", {
        "S": [["a"], ["a", "b"]],
    }


# ---------------------------------------------------------------------------
# Helper to build a parser from a grammar-factory
# ---------------------------------------------------------------------------

def _build(factory):
    start, grammar = factory()
    return PredictiveParser(start, grammar)


# ===================================================================
# 1. is_terminal / is_nonterminal
# ===================================================================

class TestSymbolClassification:
    def setup_method(self):
        self.p = _build(_expr_grammar)

    def test_terminals(self):
        assert self.p.is_terminal("id")
        assert self.p.is_terminal("+")
        assert self.p.is_terminal("*")
        assert self.p.is_terminal("(")
        assert self.p.is_terminal(")")

    def test_nonterminals(self):
        assert self.p.is_nonterminal("E")
        assert self.p.is_nonterminal("Ep")
        assert self.p.is_nonterminal("T")
        assert self.p.is_nonterminal("Tp")
        assert self.p.is_nonterminal("F")

    def test_empty_string_is_neither(self):
        assert not self.p.is_terminal("")
        assert not self.p.is_nonterminal("")

    def test_unknown_symbol_is_neither(self):
        assert not self.p.is_terminal("unknown")
        assert not self.p.is_nonterminal("unknown")

    def test_mutual_exclusion(self):
        for sym in ["id", "+", "*", "(", ")"]:
            assert self.p.is_terminal(sym) and not self.p.is_nonterminal(sym)
        for sym in ["E", "Ep", "T", "Tp", "F"]:
            assert self.p.is_nonterminal(sym) and not self.p.is_terminal(sym)


# ===================================================================
# 2. Nullable
# ===================================================================

class TestNullable:
    def test_epsilon_production_nullable(self):
        p = _build(_nullable_prefix_grammar)
        assert p.null_dict["A"] is True

    def test_non_nullable(self):
        p = _build(_nullable_prefix_grammar)
        assert p.null_dict["B"] is False
        assert p.null_dict["S"] is False

    def test_all_nullable(self):
        p = _build(_all_nullable_grammar)
        assert p.null_dict["A"] is True
        assert p.null_dict["B"] is True
        assert p.null_dict["S"] is True

    def test_nullable_method_sequence(self):
        p = _build(_all_nullable_grammar)
        assert p.nullable(["A", "B"]) is True

    def test_nullable_method_non_nullable_sequence(self):
        p = _build(_nullable_prefix_grammar)
        assert p.nullable(["A", "B"]) is False

    def test_nullable_empty(self):
        p = _build(_nullable_prefix_grammar)
        assert p.nullable([]) is True

    def test_expr_grammar_nullable(self):
        p = _build(_expr_grammar)
        assert p.null_dict["Ep"] is True
        assert p.null_dict["Tp"] is True
        assert p.null_dict["E"] is False
        assert p.null_dict["T"] is False
        assert p.null_dict["F"] is False


# ===================================================================
# 3. FIRST sets
# ===================================================================

class TestFirst:
    def test_terminal_first(self):
        p = _build(_expr_grammar)
        assert p.first_dict["id"] == {"id"}
        assert p.first_dict["+"] == {"+"}

    def test_simple_nonterminal(self):
        p = _build(_single_terminal_grammar)
        assert p.first_dict["S"] == {"x"}

    def test_expr_grammar_first(self):
        p = _build(_expr_grammar)
        assert p.first_dict["F"] == {"(", "id"}
        assert p.first_dict["T"] == {"(", "id"}
        assert p.first_dict["E"] == {"(", "id"}
        assert EPSILON in p.first_dict["Ep"]
        assert "+" in p.first_dict["Ep"]
        assert EPSILON in p.first_dict["Tp"]
        assert "*" in p.first_dict["Tp"]

    def test_nullable_prefix_first(self):
        """S → A B, A → a | ε, B → b.
        FIRST(S) must include 'b' because A can derive ε.
        """
        p = _build(_nullable_prefix_grammar)
        assert "a" in p.first_dict["S"]
        assert "b" in p.first_dict["S"], (
            "FIRST(S) must contain 'b' since A is nullable"
        )
        assert EPSILON not in p.first_dict["S"], (
            "ε must NOT be in FIRST(S) since S cannot derive ε (B is not nullable)"
        )

    def test_all_nullable_first(self):
        """S → A B, A → a | ε, B → b | ε.
        FIRST(S) = {a, b, ε}
        """
        p = _build(_all_nullable_grammar)
        assert p.first_dict["S"] == {"a", "b", EPSILON}

    def test_chained_nullable_first(self):
        """S → A B C, A → a|ε, B → b|ε, C → c.
        FIRST(S) = {a, b, c}  (no ε because C is not nullable)
        """
        p = _build(_chained_nullable_grammar)
        assert p.first_dict["S"] == {"a", "b", "c"}

    def test_first_of_sequence(self):
        """first(["A", "B"]) where A nullable should include FIRST(B)."""
        p = _build(_nullable_prefix_grammar)
        result = p.first(["A", "B"])
        assert "a" in result
        assert "b" in result
        assert EPSILON not in result, (
            "ε should not be in FIRST(A B) when B is not nullable"
        )

    def test_first_of_all_nullable_sequence(self):
        p = _build(_all_nullable_grammar)
        result = p.first(["A", "B"])
        assert result == {"a", "b", EPSILON}


# ===================================================================
# 4. FOLLOW sets
# ===================================================================

class TestFollow:
    def test_start_symbol_has_dollar(self):
        p = _build(_expr_grammar)
        assert "$" in p.follow_dict["E"]

    def test_expr_follow(self):
        p = _build(_expr_grammar)
        assert p.follow_dict["E"] == {")", "$"}
        assert p.follow_dict["Ep"] == {")", "$"}
        assert p.follow_dict["T"] == {"+", ")", "$"}
        assert p.follow_dict["Tp"] == {"+", ")", "$"}
        assert p.follow_dict["F"] == {"*", "+", ")", "$"}

    def test_nullable_prefix_follow(self):
        p = _build(_nullable_prefix_grammar)
        assert "b" in p.follow_dict["A"], (
            "FOLLOW(A) must contain 'b' from S → A·B"
        )
        assert "$" in p.follow_dict["S"]
        assert "$" in p.follow_dict["B"]

    def test_chained_nullable_follow(self):
        p = _build(_chained_nullable_grammar)
        assert "b" in p.follow_dict["A"]
        assert "c" in p.follow_dict["A"], (
            "FOLLOW(A) must contain 'c' because B is nullable in S → A B·C"
        )
        assert "c" in p.follow_dict["B"]


# ===================================================================
# 5. Parse table
# ===================================================================

class TestParseTable:
    def test_expr_table_entries(self):
        p = _build(_expr_grammar)
        assert p.table["E", "id"] == ["T", "Ep"]
        assert p.table["E", "("] == ["T", "Ep"]
        assert p.table["F", "id"] == ["id"]
        assert p.table["F", "("] == ["(", "E", ")"]
        assert p.table["Ep", "+"] == ["+", "T", "Ep"]

    def test_epsilon_entries(self):
        p = _build(_expr_grammar)
        assert p.table["Ep", ")"] == [EPSILON]
        assert p.table["Ep", "$"] == [EPSILON]
        assert p.table["Tp", "+"] == [EPSILON]
        assert p.table["Tp", ")"] == [EPSILON]
        assert p.table["Tp", "$"] == [EPSILON]

    def test_nullable_prefix_table(self):
        """S → A B, A → a|ε, B → b.
        Table must have (S, b) → A B  (because A can be ε, exposing b).
        """
        p = _build(_nullable_prefix_grammar)
        assert p.table["S", "a"] == ["A", "B"]
        assert ("S", "b") in p.table, (
            "Table must contain (S, b) entry since A is nullable"
        )
        assert p.table["S", "b"] == ["A", "B"]


# ===================================================================
# 6. match — acceptance / rejection
# ===================================================================

class TestMatch:
    def test_expr_valid(self):
        p = _build(_expr_grammar)
        assert p.match(["id"]) is True

    def test_expr_valid_addition(self):
        p = _build(_expr_grammar)
        assert p.match(["id", "+", "id"]) is True

    def test_expr_valid_complex(self):
        p = _build(_expr_grammar)
        assert p.match(["id", "+", "id", "*", "id"]) is True

    def test_expr_valid_parens(self):
        p = _build(_expr_grammar)
        assert p.match(["(", "id", "+", "id", ")", "*", "id"]) is True

    def test_expr_reject_empty(self):
        p = _build(_expr_grammar)
        assert p.match([]) is False

    def test_expr_reject_invalid(self):
        p = _build(_expr_grammar)
        assert p.match(["+"]) is False

    def test_expr_reject_unbalanced_parens(self):
        p = _build(_expr_grammar)
        assert p.match(["(", "id"]) is False

    def test_nullable_prefix_match_a_b(self):
        p = _build(_nullable_prefix_grammar)
        assert p.match(["a", "b"]) is True

    def test_nullable_prefix_match_b_only(self):
        """When A derives ε, input 'b' should be accepted."""
        p = _build(_nullable_prefix_grammar)
        assert p.match(["b"]) is True

    def test_all_nullable_match_empty(self):
        p = _build(_all_nullable_grammar)
        assert p.match([]) is True

    def test_all_nullable_match_a(self):
        p = _build(_all_nullable_grammar)
        assert p.match(["a"]) is True

    def test_all_nullable_match_b(self):
        p = _build(_all_nullable_grammar)
        assert p.match(["b"]) is True

    def test_all_nullable_match_ab(self):
        p = _build(_all_nullable_grammar)
        assert p.match(["a", "b"]) is True

    def test_all_nullable_reject_ba(self):
        p = _build(_all_nullable_grammar)
        assert p.match(["b", "a"]) is False

    def test_chained_match(self):
        p = _build(_chained_nullable_grammar)
        assert p.match(["a", "b", "c"]) is True
        assert p.match(["b", "c"]) is True
        assert p.match(["a", "c"]) is True
        assert p.match(["c"]) is True


# ===================================================================
# 7. match must NOT mutate the input list
# ===================================================================

class TestMatchNoMutation:
    def test_match_does_not_mutate(self):
        p = _build(_expr_grammar)
        seq = ["id", "+", "id"]
        original = list(seq)
        p.match(seq)
        assert seq == original, "match() must not mutate the input list"

    def test_verbose_match_does_not_mutate(self):
        p = _build(_expr_grammar)
        seq = ["id", "+", "id"]
        original = list(seq)
        p.verbose_match(seq)
        assert seq == original, "verbose_match() must not mutate the input list"

    def test_double_match_same_result(self):
        """Calling match twice on the same list must give the same result."""
        p = _build(_expr_grammar)
        seq = ["id"]
        assert p.match(seq) is True
        assert p.match(seq) is True


# ===================================================================
# 8. verbose_match (basic smoke test)
# ===================================================================

class TestVerboseMatch:
    def test_verbose_accept(self, capsys):
        p = _build(_expr_grammar)
        assert p.verbose_match(["id"]) is True
        captured = capsys.readouterr()
        assert "match" in captured.out.lower()

    def test_verbose_reject(self, capsys):
        p = _build(_expr_grammar)
        assert p.verbose_match(["+"]) is False


# ===================================================================
# 9. LL(1) conflict detection
# ===================================================================

class TestConflictDetection:
    def test_ambiguous_grammar_raises(self):
        """A non-LL(1) grammar should be detected (conflict on same cell)."""
        start, grammar = _ambiguous_grammar()
        with pytest.raises(ValueError, match="[Cc]onflict"):
            PredictiveParser(start, grammar)


# ===================================================================
# 10. Edge cases
# ===================================================================

class TestEdgeCases:
    def test_single_terminal_grammar(self):
        p = _build(_single_terminal_grammar)
        assert p.match(["x"]) is True
        assert p.match(["y"]) is False
        assert p.match([]) is False

    def test_terminals_and_nonterminals_sets(self):
        p = _build(_expr_grammar)
        assert "id" in p.terminals
        assert "+" in p.terminals
        assert "*" in p.terminals
        assert "(" in p.terminals
        assert ")" in p.terminals
        assert "E" in p.nonterminals
        assert "T" in p.nonterminals
        assert "F" in p.nonterminals


# ===================================================================
# 11. Grammar validation
# ===================================================================

class TestGrammarValidation:
    def test_undefined_start_symbol(self):
        with pytest.raises(ValueError, match="start symbol"):
            PredictiveParser("X", {"S": [["a"]]})

    def test_undefined_nonterminal_in_production(self):
        with pytest.raises(ValueError, match="no.*defining rule"):
            PredictiveParser("S", {"S": [["A"]]})

    def test_valid_grammar_accepted(self):
        PredictiveParser("S", {"S": [["a"]]})


# ===================================================================
# 12. detailed_match diagnostics
# ===================================================================

class TestDetailedMatch:
    def test_success_result(self):
        p = _build(_expr_grammar)
        result = p.detailed_match(["id"])
        assert result.success is True
        assert bool(result) is True

    def test_failure_has_position_and_expected(self):
        p = _build(_expr_grammar)
        result = p.detailed_match(["+"])
        assert result.success is False
        assert result.position == 0
        assert result.got == "+"
        assert len(result.expected) > 0
        assert "(" in result.expected
        assert "id" in result.expected

    def test_failure_unbalanced_parens(self):
        p = _build(_expr_grammar)
        result = p.detailed_match(["(", "id"])
        assert result.success is False
        assert result.position > 0
        assert ")" in result.expected

    def test_match_result_repr(self):
        r = MatchResult(success=True)
        assert "success=True" in repr(r)
        r = MatchResult(success=False, position=3, got="x")
        assert "success=False" in repr(r)
        assert "position=3" in repr(r)


# ===================================================================
# 13. __repr__
# ===================================================================

class TestRepr:
    def test_repr_format(self):
        p = _build(_expr_grammar)
        r = repr(p)
        assert "PredictiveParser" in r
        assert "'E'" in r
        assert "nonterminals=" in r
        assert "terminals=" in r


# ===================================================================
# 14. EPSILON sentinel
# ===================================================================

class TestEpsilon:
    def test_epsilon_is_empty_string(self):
        assert EPSILON == ""

    def test_epsilon_production_uses_sentinel(self):
        p = _build(_expr_grammar)
        assert p.table["Ep", ")"] == [EPSILON]
        assert p.table["Ep", "$"] == [EPSILON]


# ===================================================================
# 15. TokenLike / bring-your-own-lexer support
# ===================================================================


@dataclass
class _PlyStyleToken:
    """Mimics a PLY LexToken: has .type plus arbitrary extra attributes."""

    type: str
    value: str = ""
    lineno: int = 0
    lexpos: int = 0


class TestTokenLikeInput:
    def test_simple_token_satisfies_protocol(self):
        t = SimpleToken(type="id", value="x")
        assert isinstance(t, TokenLike)

    def test_ply_style_token_satisfies_protocol(self):
        t = _PlyStyleToken(type="id", value="x", lineno=1, lexpos=0)
        assert isinstance(t, TokenLike)

    def test_match_accepts_simple_tokens(self):
        p = _build(_expr_grammar)
        tokens = [SimpleToken(type="id"), SimpleToken(type="+"), SimpleToken(type="id")]
        assert p.match(tokens) is True

    def test_match_accepts_ply_style_tokens(self):
        p = _build(_expr_grammar)
        tokens = [
            _PlyStyleToken(type="id", value="a", lineno=1, lexpos=0),
            _PlyStyleToken(type="+", value="+", lineno=1, lexpos=2),
            _PlyStyleToken(type="id", value="b", lineno=1, lexpos=4),
        ]
        assert p.match(tokens) is True

    def test_match_accepts_mixed_strings_and_tokens(self):
        """Mixed input works: strings are auto-wrapped, tokens pass through."""
        p = _build(_expr_grammar)
        mixed = ["id", SimpleToken(type="+"), "id"]
        assert p.match(mixed) is True

    def test_detailed_match_reports_token_type_on_failure(self):
        """MatchResult.got must be the .type string, not the object repr."""
        p = _build(_expr_grammar)
        result = p.detailed_match([SimpleToken(type="+")])
        assert result.success is False
        assert result.got == "+"
        assert "id" in result.expected

    def test_string_input_still_reports_strings(self):
        """Backward compat: passing list[str] yields string .got values."""
        p = _build(_expr_grammar)
        result = p.detailed_match(["+"])
        assert result.got == "+"
        assert isinstance(result.got, str)

    def test_empty_token_list_rejected(self):
        p = _build(_expr_grammar)
        assert p.match([]) is False
        result = p.detailed_match([])
        assert result.success is False
        assert result.got == "$"

    def test_tokens_input_not_mutated(self):
        p = _build(_expr_grammar)
        tokens = [SimpleToken(type="id"), SimpleToken(type="+"), SimpleToken(type="id")]
        original = list(tokens)
        p.match(tokens)
        assert tokens == original

    def test_verbose_match_with_tokens(self, capsys):
        p = _build(_expr_grammar)
        tokens = [SimpleToken(type="id")]
        assert p.verbose_match(tokens) is True
        captured = capsys.readouterr()
        assert "match" in captured.out.lower()
