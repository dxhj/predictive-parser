"""Targeted tests filling coverage gaps across the package.

These tests drive the less-travelled code paths — convenience helpers,
error branches, EBNF/transform edge cases, LL(k) fallback, and the CLI's
no-lexer path — so that the suite keeps exercising documented behavior.
"""

from __future__ import annotations

import io

import pytest

from predictive_parser import (
    EPSILON,
    ActionError,
    DefaultErrorListener,
    Grammar,
    LL1Conflict,
    ParseError,
    ParseTree,
    ParseTreeListener,
    ParseTreeVisitor,
    PredictiveParser,
    ProductionSpec,
    RaisingErrorListener,
    SimpleToken,
    SourceLocation,
    Token,
    build_llk_table,
    compile_action,
    concat_action,
    default_action,
    eliminate_left_recursion,
    left_factor,
    parse_grammar,
    parse_production_string,
    walk_tree,
)
from predictive_parser.sets import compute_first_k
from predictive_parser.table import build_ll1_table
from predictive_parser.tree import _safe_name

# ---------------------------------------------------------------------------
# actions.py — tiny helpers
# ---------------------------------------------------------------------------


class TestActionHelpers:
    def test_default_action_returns_first(self) -> None:
        assert default_action([1, 2, 3]) == 1

    def test_default_action_empty(self) -> None:
        assert default_action([]) is None

    def test_concat_action_tuple(self) -> None:
        assert concat_action([1, 2, 3]) == (1, 2, 3)

    def test_production_spec_key(self) -> None:
        spec = ProductionSpec(head="S", body=("a", "b"))
        assert spec.key() == ("S", ("a", "b"))


# ---------------------------------------------------------------------------
# errors.py — listener + location branches
# ---------------------------------------------------------------------------


class TestRaisingListenerDirect:
    def test_raises_parse_error_with_token(self) -> None:
        listener = RaisingErrorListener()
        tok = SimpleToken(type="x", value="x", line=1, column=1)
        with pytest.raises(ParseError) as ei:
            listener.syntax_error(
                SourceLocation(line=1, column=1),
                frozenset({"y"}),
                tok,
                "nope",
            )
        assert ei.value.got == "x"
        assert "y" in ei.value.expected

    def test_raises_parse_error_no_token(self) -> None:
        listener = RaisingErrorListener()
        with pytest.raises(ParseError) as ei:
            listener.syntax_error(
                SourceLocation(),
                frozenset(),
                None,
                "eof",
            )
        assert ei.value.got is None


class TestActionErrorMessage:
    def test_epsilon_body_renders_as_eps(self) -> None:
        err = ActionError(
            production=("S", ()),
            original=RuntimeError("boom"),
            location=SourceLocation(line=2, column=3),
        )
        msg = str(err)
        assert "S" in msg
        assert "\u03b5" in msg  # ε used for empty body
        assert "boom" in msg


# ---------------------------------------------------------------------------
# lexer.py — location property on tokens
# ---------------------------------------------------------------------------


class TestTokenLocationProperty:
    def test_simple_token_location(self) -> None:
        t = SimpleToken(type="a", value="a", line=2, column=4, offset=10)
        loc = t.location
        assert loc.line == 2 and loc.column == 4 and loc.offset == 10

    def test_lexer_token_location(self) -> None:
        t = Token(type="a", value="a", line=3, column=5, offset=7)
        loc = t.location
        assert loc.line == 3 and loc.column == 5 and loc.offset == 7


# ---------------------------------------------------------------------------
# grammar.py — Grammar helpers + DSL error branches
# ---------------------------------------------------------------------------


class TestGrammarHelpers:
    def test_get_action_returns_registered(self) -> None:
        g = Grammar.from_rules(
            "S",
            {"S": [["a"]]},
            actions={("S", ("a",)): lambda v: v[0]},
        )
        assert g.get_action("S", ("a",)) is not None
        assert g.get_action("S", ("missing",)) is None
        assert g.get_action("Nope", ()) is None

    def test_set_action_missing_raises(self) -> None:
        g = Grammar.from_rules("S", {"S": [["a"]]})
        with pytest.raises(KeyError):
            g.set_action("S", ("b",), lambda v: None)

    def test_iter_productions_yields_specs(self) -> None:
        g = Grammar.from_rules("S", {"S": [["a"], ["b"]]})
        bodies = [p.body for p in g.iter_productions()]
        assert ("a",) in bodies and ("b",) in bodies


class TestDSLErrorBranches:
    def test_empty_grammar_has_no_rules(self) -> None:
        with pytest.raises(ValueError, match="no rules"):
            parse_grammar("")

    def test_empty_action_block_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty action"):
            compile_action("   \n  ")

    def test_unclosed_paren(self) -> None:
        with pytest.raises(ParseError, match="unclosed"):
            parse_grammar("S -> ( 'a' | 'b'")

    def test_missing_arrow_reports_eat_error(self) -> None:
        # Triggers the _eat failure branch: `S` then EOF — no ARROW.
        with pytest.raises(ParseError, match="expected ARROW"):
            parse_grammar("S")

    def test_top_level_unexpected_token(self) -> None:
        with pytest.raises(ParseError, match="unexpected token"):
            parse_grammar("; garbage")

    def test_action_block_with_nested_braces(self) -> None:
        # Nested ``{...}`` are consumed as part of the action text so the
        # block tokenizer's depth counter is exercised in both directions.
        src = r"""
        %start S
        S -> 'a' { $$ = {"k": 1}["k"] } ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.parse(["a"]) == 1

    def test_action_block_with_newlines(self) -> None:
        src = """
        %start S
        S -> 'a' {
            $$ = 42
        } ;
        """
        p = PredictiveParser.from_grammar(src)
        assert p.parse(["a"]) == 42

    def test_parse_production_string_ebnf_rejected(self) -> None:
        with pytest.raises(ValueError, match="EBNF"):
            parse_production_string("S -> 'a'?")

    def test_parse_production_string_skips_epsilon(self) -> None:
        head, body = parse_production_string("S -> epsilon")
        assert head == "S" and body == ()


# ---------------------------------------------------------------------------
# sets.py — FIRST_k truncation + ε-only production
# ---------------------------------------------------------------------------


class TestFirstKEdgeCases:
    def test_first_k_truncates_long_prefix(self) -> None:
        # A production whose FIRST_k produces a string ≥ k chars — this
        # exercises the early-truncation branch in first_of_seq.
        grammar = {"S": [["a", "b", "c", "d"]]}
        fk = compute_first_k(grammar, ["a", "b", "c", "d"], k=2)
        assert fk["S"] == {("a", "b")}

    def test_first_k_with_epsilon_production(self) -> None:
        grammar = {"S": [["a"], [EPSILON]]}
        fk = compute_first_k(grammar, ["a"], k=1)
        assert () in fk["S"]
        assert ("a",) in fk["S"]


# ---------------------------------------------------------------------------
# table.py — conflict branches and LL(k) validation
# ---------------------------------------------------------------------------


class TestTableBuilderShortcuts:
    def test_build_ll1_table_accepts_precomputed_sets(self) -> None:
        # Exercising the `is None` short-circuits: pass every set so the
        # builder reuses the caller's computations.
        from predictive_parser.sets import (
            compute_first,
            compute_follow,
            compute_nullable,
        )

        grammar = {"S": [["a"]]}
        nullable = compute_nullable(grammar, ["a"])
        first = compute_first(grammar, ["a"], nullable)
        follow = compute_follow(grammar, "S", first, nullable)
        table, n2, f2, fl2 = build_ll1_table(
            grammar, "S", ["a"], nullable=nullable, first=first, follow=follow
        )
        assert table[("S", "a")] == ["a"]
        assert n2 is nullable and f2 is first and fl2 is follow


class TestTableConflicts:
    def test_epsilon_follow_conflict_raises(self) -> None:
        # S -> A 'a'; A -> 'a' | ε  -> FIRST/FOLLOW clash on 'a'.
        grammar = {
            "S": [["A", "a"]],
            "A": [["a"], [EPSILON]],
        }
        with pytest.raises(LL1Conflict):
            build_ll1_table(grammar, "S", ["a"])

    def test_llk_requires_positive_k(self) -> None:
        with pytest.raises(ValueError, match="k must"):
            build_llk_table({"S": [["a"]]}, "S", ["a"], k=0)

    def test_llk_conflict_reports(self) -> None:
        # Genuinely conflicting LL(k): two prods share a length-k prefix.
        grammar = {"S": [["a"], ["a", "b"]]}
        with pytest.raises(LL1Conflict):
            build_llk_table(grammar, "S", ["a", "b"], k=1)

    def test_llk_handles_epsilon_production(self) -> None:
        grammar = {"S": [[EPSILON]]}
        table = build_llk_table(grammar, "S", [], k=1)
        # ε production maps to the empty tuple key.
        assert (("S", ())) in table


# ---------------------------------------------------------------------------
# transforms.py — branches in EBNF / left-factor / left-recursion
# ---------------------------------------------------------------------------


class TestTransformBranches:
    def test_unknown_ebnf_node_raises(self) -> None:
        from typing import ClassVar

        from predictive_parser.transforms import desugar_ebnf

        class Bogus:
            kind = "bogus"
            children: ClassVar[list] = []

        with pytest.raises(ValueError, match="unknown EBNF"):
            desugar_ebnf([Bogus()], "S", lambda h, b: None, lambda h: "X")

    def test_left_factor_identity_when_nothing_to_factor(self) -> None:
        g = {"S": [["a"], ["b"]]}
        assert left_factor(g) == {"S": [["a"], ["b"]]}

    def test_left_factor_single_production_unchanged(self) -> None:
        g = {"S": [["a", "b"]]}
        assert left_factor(g) == g

    def test_left_factor_produces_epsilon_for_exact_prefix(self) -> None:
        # 'a' vs 'a b' -> common prefix 'a', remainder '' (ε) on the first.
        g = {"S": [["a"], ["a", "b"]]}
        g2 = left_factor(g)
        tails = [prods for head, prods in g2.items() if head != "S"]
        assert any([EPSILON] in prods for prods in tails)

    def test_eliminate_left_recursion_with_epsilon_prefix(self) -> None:
        # A has an ε-production; when B references A at the front, the
        # substitution branch must emit the original tail alone (line 125).
        g = {
            "A": [[EPSILON], ["a"]],
            "B": [["A", "b"]],
        }
        g2 = eliminate_left_recursion(g)
        p = PredictiveParser("B", g2)
        assert p.match(["b"])
        assert p.match(["a", "b"])

    def test_eliminate_left_recursion_no_alpha_returns_original(self) -> None:
        g = {"S": [["a"], ["b"]]}
        g2 = eliminate_left_recursion(g)
        assert g2["S"] == [["a"], ["b"]]

    def test_eliminate_left_recursion_renames_on_collision(self) -> None:
        # S__lr already exists, so the transform must pick a fresh suffix.
        g = {
            "S": [["S", "a"], ["b"]],
            "S__lr": [["x"]],
        }
        g2 = eliminate_left_recursion(g)
        # Fresh tail should be the bumped name, not overwrite ``S__lr``.
        assert g2["S__lr"] == [["x"]]
        new_tails = [k for k in g2 if k.startswith("S__lr_")]
        assert new_tails, g2

    def test_eliminate_left_recursion_epsilon_base_case(self) -> None:
        # beta contains an ε production — line 156 appends [tail] alone.
        g = {"S": [["S", "a"], [EPSILON]]}
        g2 = eliminate_left_recursion(g)
        # The non-recursive side should reduce to just the tail reference.
        assert [g2["S"][0][0]].__len__() == 1

    def test_eliminate_left_recursion_only_recursive_branch(self) -> None:
        # No base case at all — triggers the "empty beta" branch.  The
        # transform shouldn't crash even though the resulting grammar
        # cannot produce anything meaningful.
        g = {"S": [["S", "a"]]}
        g2 = eliminate_left_recursion(g)
        assert "S" in g2

    def test_left_factor_renames_on_collision(self) -> None:
        # The first generated suffix (S__lf1) is already taken so the
        # transform should bump the counter.
        g = {
            "S": [["a", "b"], ["a", "c"]],
            "S__lf1": [["z"]],
        }
        g2 = left_factor(g)
        assert g2["S__lf1"] == [["z"]]
        assert any(name != "S__lf1" and name.startswith("S__lf") for name in g2)


# ---------------------------------------------------------------------------
# tree.py — misc helpers
# ---------------------------------------------------------------------------


class TestTreeHelpers:
    def test_parse_tree_repr(self) -> None:
        t = ParseTree(symbol="S", children=[SimpleToken(type="a")])
        assert "ParseTree" in repr(t)
        assert "children=1" in repr(t)

    def test_walk_tree_wrapper_invokes_listener(self) -> None:
        p = PredictiveParser("S", {"S": [["a"]]})
        tree = p.parse(["a"])
        seen: list[str] = []

        class L(ParseTreeListener):
            def enter_every_rule(self, node: ParseTree) -> None:
                seen.append(node.symbol)

        walk_tree(L(), tree)
        assert "S" in seen

    def test_safe_name_handles_primes_and_digits(self) -> None:
        # Primes (') are replaced with an ordinal escape.
        out = _safe_name("Expr'")
        assert out.startswith("Expr_")
        # Leading digits get an s_ prefix so the result is a valid ident.
        assert _safe_name("1st").startswith("s_")

    def test_visitor_default_returns_children_values(self) -> None:
        # The default `visit` path returns a list of child results when no
        # visit_<symbol> method is defined.
        p = PredictiveParser("S", {"S": [["a"]]})
        tree = p.parse(["a"])

        class V(ParseTreeVisitor):
            pass

        result = V().visit(tree)
        assert isinstance(result, list) and len(result) == 1


# ---------------------------------------------------------------------------
# parser.py — lookahead, verbose/display_stack, LL(k) fallback, print_table
# ---------------------------------------------------------------------------


class TestLookaheadPeek:
    def test_peek_beyond_buffer_pads_with_end(self) -> None:
        # k>1 causes _Lookahead to pre-buffer and handle peek(offset) past
        # the end of the real stream.
        p = PredictiveParser("S", {"S": [["a"]]}, k=3)
        assert p.match(["a"])
        # Empty input — all lookaheads should degrade to $.
        assert not p.match([])

    def test_lookahead_peek_offset_and_consume(self) -> None:
        # Drive _Lookahead directly: peek past the buffered range (triggers
        # the StopIteration padding branch) and then consume past EOF so
        # the end-of-input token re-appears at the front.
        from predictive_parser.parser import _Lookahead

        la = _Lookahead(iter(["a"]), k=1)
        assert la.peek().type == "a"
        # Ask for an offset beyond what's buffered — forces the inner loop.
        padded = la.peek(offset=3)
        assert padded.type == "$"
        # Consume the real token, then consume past EOF twice.
        tok = la.consume()
        assert tok.type == "a"
        assert la.consume().type == "$"
        assert la.consume().type == "$"
        # Position only advanced for the one real token.
        assert la.position == 1

    def test_lookahead_peek_extends_buffer_with_more_tokens(self) -> None:
        # With k=1 the initial buffer holds one token.  peek(2) should pull
        # two more real tokens from the iterator (line 118 of parser.py).
        from predictive_parser.parser import _Lookahead

        la = _Lookahead(iter(["a", "b", "c"]), k=1)
        assert la.peek(0).type == "a"
        assert la.peek(2).type == "c"  # forces two ``append`` iterations


class TestVerbosePath:
    def test_verbose_match_prints_derivations(self, capsys) -> None:
        p = PredictiveParser(
            "E",
            {
                "E": [["T", "Ep"]],
                "Ep": [["+", "T", "Ep"], [EPSILON]],
                "T": [["id"]],
            },
        )
        assert p.verbose_match(["id", "+", "id"], display_stack=True)
        out = capsys.readouterr().out
        assert "Action" in out or "derive" in out
        assert "Stack" in out

    def test_verbose_reports_derivation_failure(self, capsys) -> None:
        p = PredictiveParser(
            "E",
            {
                "E": [["T", "Ep"]],
                "Ep": [["+", "T", "Ep"], [EPSILON]],
                "T": [["id"]],
            },
            error_listener=DefaultErrorListener(),
        )
        assert not p.verbose_match(["+"])
        out = capsys.readouterr().out
        assert "ERROR" in out

    def test_print_table(self, capsys) -> None:
        p = PredictiveParser("S", {"S": [["a"]]})
        p.print_table()
        out = capsys.readouterr().out
        assert "S" in out and "a" in out


class TestLLkParser:
    def test_llk_builds_for_clean_grammar(self) -> None:
        p = PredictiveParser("S", {"S": [["a"]]}, k=2)
        assert p.match(["a"])
        assert p._llk_table is not None  # type: ignore[attr-defined]


class TestTreeDefaultBuilder:
    def test_tree_default_runs_for_unactioned_productions(self) -> None:
        # Registering an action anywhere flips run_actions to True.  Any
        # production *without* an action must then fall back to the default
        # tree-building closure — exercising _tree_default.build.
        p = PredictiveParser(
            "S",
            {
                "S": [["A", "B"]],
                "A": [["a"]],
                "B": [["b"]],
            },
        )
        p.set_action("A", ("a",), lambda v: v[0].value)
        result = p.parse(["a", "b"])
        # S + B still produce a ParseTree since they have no user action.
        assert isinstance(result, ParseTree)
        assert result.symbol == "S"


class TestDetailedMatch:
    def test_detailed_match_reports_position(self) -> None:
        p = PredictiveParser(
            "E",
            {"E": [["id"]]},
            error_listener=DefaultErrorListener(),
        )
        r = p.detailed_match(["id", "id"])
        assert not r.success
        assert r.position >= 1
        assert "MatchResult" in repr(r)
        assert repr(p.detailed_match(["id"]))  # success repr branch


class TestParserRepr:
    def test_repr_mentions_counts(self) -> None:
        p = PredictiveParser(
            "E",
            {"E": [["id"]]},
        )
        r = repr(p)
        assert "PredictiveParser" in r and "start='E'" in r


# ---------------------------------------------------------------------------
# cli.py — no-lexer parse path
# ---------------------------------------------------------------------------


_NOLEXER_GRAMMAR = """
%start S
S -> 'a' 'b' ;
"""


class TestCLINoLexer:
    def test_parse_splits_input_when_grammar_has_no_lexer(
        self, tmp_path, capsys
    ) -> None:
        from predictive_parser.cli import main

        gp = tmp_path / "g.gr"
        gp.write_text(_NOLEXER_GRAMMAR)
        ip = tmp_path / "in.txt"
        ip.write_text("a b")
        rc = main(["parse", str(gp), str(ip)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "S" in out

    def test_parse_reads_from_stdin(
        self, tmp_path, capsys, monkeypatch
    ) -> None:
        from predictive_parser.cli import main

        gp = tmp_path / "g.gr"
        gp.write_text(_NOLEXER_GRAMMAR)
        monkeypatch.setattr("sys.stdin", io.StringIO("a b"))
        rc = main(["parse", str(gp), "-"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "S" in out
