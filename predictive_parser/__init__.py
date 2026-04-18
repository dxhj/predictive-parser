"""predictive-parser — a small LL(1) predictive parser for Python.

Public API re-exports.  The legacy top-level module ``predictive`` is still
available as a compatibility shim.
"""

from __future__ import annotations

from .actions import Action, ProductionSpec, concat_action, default_action
from .errors import (
    ActionError,
    DefaultErrorListener,
    ErrorListener,
    LexerError,
    ParseError,
    RaisingErrorListener,
    SourceLocation,
)
from .grammar import (
    DSLResult,
    Grammar,
    compile_action,
    parse_grammar,
    parse_grammar_file,
    parse_production_string,
)
from .lexer import (
    Lexer,
    SimpleToken,
    Token,
    TokenInput,
    TokenLike,
    TokenRule,
    TokenStream,
    from_ply_lexer,
    get_location,
    normalize_tokens,
)
from .parser import MatchResult, PredictiveParser
from .serialization import dump_tables, from_json, load_tables, to_json
from .sets import END_MARK, EPSILON
from .table import LL1Conflict, build_ll1_table, build_llk_table, index_table
from .transforms import desugar_ebnf, eliminate_left_recursion, left_factor
from .tree import (
    ParseTree,
    ParseTreeListener,
    ParseTreeVisitor,
    tree_location,
    walk_tree,
)

__version__ = "2.0.0"

__all__ = [
    "END_MARK",
    "EPSILON",
    "Action",
    "ActionError",
    "DSLResult",
    "DefaultErrorListener",
    "ErrorListener",
    "Grammar",
    "LL1Conflict",
    "Lexer",
    "LexerError",
    "MatchResult",
    "ParseError",
    "ParseTree",
    "ParseTreeListener",
    "ParseTreeVisitor",
    "PredictiveParser",
    "ProductionSpec",
    "RaisingErrorListener",
    "SimpleToken",
    "SourceLocation",
    "Token",
    "TokenInput",
    "TokenLike",
    "TokenRule",
    "TokenStream",
    "__version__",
    "build_ll1_table",
    "build_llk_table",
    "compile_action",
    "concat_action",
    "default_action",
    "desugar_ebnf",
    "dump_tables",
    "eliminate_left_recursion",
    "from_json",
    "from_ply_lexer",
    "get_location",
    "index_table",
    "left_factor",
    "load_tables",
    "normalize_tokens",
    "parse_grammar",
    "parse_grammar_file",
    "parse_production_string",
    "to_json",
    "tree_location",
    "walk_tree",
]
