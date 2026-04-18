"""A tiny Lisp interpreter built on ``predictive_parser``.

The parser produces a custom AST (``Number``, ``String``, ``Symbol``,
``SList``) via semantic actions, and a classic double-dispatch
*Visitor* walks it.  Two visitors are provided:

* :class:`Evaluator` — runs the program, returning a value.
* :class:`Formatter`  — prints the AST back as Lisp source (``(pretty)``).

Supported language subset
-------------------------

* Literals: integers, floats, double-quoted strings, symbols.
* Constants: ``true``, ``false``, ``nil``.
* Quoting: ``'x`` which desugars to ``(quote x)``.
* Special forms: ``quote``, ``if``, ``define``, ``set!``, ``lambda``,
  ``let``, ``begin``, ``cond``, ``and``, ``or``.
* Built-ins: arithmetic (``+ - * /``), comparison (``= < > <= >=``),
  ``not``, list ops (``list cons car cdr null? pair? length``),
  predicates (``number? symbol? string? procedure?``), ``eq?``,
  ``print``, ``display``, ``newline``.
* Line comments starting with ``;``.

Run ``python examples/lisp_interpreter.py`` to see a handful of sample
programs evaluated.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from functools import reduce
from typing import Any, Callable, Union

from predictive_parser import PredictiveParser


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------
#
# Program -> Exprs
# Exprs   -> Expr Exprs | epsilon
# Expr    -> LP Exprs RP        ; a list
#          | QUOTE Expr         ; desugars to (quote Expr)
#          | NUMBER
#          | STRING
#          | SYMBOL
#
# SYMBOL is matched very permissively (anything that isn't whitespace,
# a paren, or a quote mark) so that ``+``, ``<=``, ``foo-bar!`` all
# lex as a single symbol.  NUMBER is tried first so that ``42`` and
# ``-3.14`` are read as numbers, while ``-`` and ``-foo`` fall through
# to SYMBOL.

GRAMMAR = r"""
%start Program
%skip  WS      = "\s+"
%skip  COMMENT = ";[^\n]*"
%token LP      = "\("
%token RP      = "\)"
%token QUOTE   = "'"
%token NUMBER  = "-?[0-9]+(\.[0-9]+)?"
%token STRING  = "\"[^\"]*\""
%token SYMBOL  = "[^\s()'\"]+"

Program -> Exprs ;
Exprs   -> Expr Exprs
        |  epsilon ;
Expr    -> LP Exprs RP
        |  QUOTE Expr
        |  NUMBER
        |  STRING
        |  SYMBOL ;
"""


class Node:
    """Base class for every AST node.

    ``accept`` is the visitor hook: it delegates to the matching
    ``visit_*`` method on the visitor.  Subclasses override it to
    achieve the double-dispatch selection at runtime.
    """

    def accept(self, visitor: "Visitor", env: "Env") -> Any:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class Number(Node):
    value: Union[int, float]

    def accept(self, visitor: "Visitor", env: "Env") -> Any:
        return visitor.visit_Number(self, env)


@dataclass(frozen=True)
class String(Node):
    value: str

    def accept(self, visitor: "Visitor", env: "Env") -> Any:
        return visitor.visit_String(self, env)


@dataclass(frozen=True)
class Symbol(Node):
    name: str

    def accept(self, visitor: "Visitor", env: "Env") -> Any:
        return visitor.visit_Symbol(self, env)


@dataclass(frozen=True)
class SList(Node):
    items: tuple[Node, ...] = ()

    def accept(self, visitor: "Visitor", env: "Env") -> Any:
        return visitor.visit_SList(self, env)


def _parse_number(text: str) -> Number:
    if "." in text:
        return Number(float(text))
    return Number(int(text))


def build_parser() -> PredictiveParser:
    parser = PredictiveParser.from_grammar(GRAMMAR)

    @parser.action("Program -> Exprs")
    def _program(values):
        return list(values[0])

    @parser.action("Exprs -> Expr Exprs")
    def _exprs_cons(values):
        head, tail = values
        return [head, *tail]

    @parser.action("Exprs -> epsilon")
    def _exprs_empty(_values):
        return []

    @parser.action("Expr -> LP Exprs RP")
    def _expr_list(values):
        return SList(tuple(values[1]))

    @parser.action("Expr -> QUOTE Expr")
    def _expr_quote(values):
        return SList((Symbol("quote"), values[1]))

    @parser.action("Expr -> NUMBER")
    def _expr_number(values):
        return _parse_number(values[0].value)

    @parser.action("Expr -> STRING")
    def _expr_string(values):
        raw = values[0].value
        return String(raw[1:-1])

    @parser.action("Expr -> SYMBOL")
    def _expr_symbol(values):
        return Symbol(values[0].value)

    return parser


class LispError(RuntimeError):
    pass


@dataclass
class Env:
    """Lexically scoped environment with parent-pointer lookup."""

    bindings: dict[str, Any] = field(default_factory=dict)
    parent: "Env | None" = None

    def lookup(self, name: str) -> Any:
        env: Env | None = self
        while env is not None:
            if name in env.bindings:
                return env.bindings[name]
            env = env.parent
        raise LispError(f"unbound symbol: {name}")

    def define(self, name: str, value: Any) -> None:
        self.bindings[name] = value

    def assign(self, name: str, value: Any) -> None:
        env: Env | None = self
        while env is not None:
            if name in env.bindings:
                env.bindings[name] = value
                return
            env = env.parent
        raise LispError(f"set!: unbound symbol: {name}")


@dataclass
class Procedure:
    """A user-defined (lambda) procedure."""

    params: tuple[str, ...]
    body: tuple[Node, ...]
    closure: Env
    evaluator: "Evaluator"
    name: str = "<lambda>"

    def __call__(self, *args: Any) -> Any:
        if len(args) != len(self.params):
            raise LispError(
                f"{self.name}: expected {len(self.params)} arg(s), got {len(args)}"
            )
        call_env = Env(dict(zip(self.params, args)), parent=self.closure)
        return self.evaluator.eval_body(self.body, call_env)


class Visitor:
    """Double-dispatch visitor base.

    Concrete visitors override the ``visit_*`` methods.  Traversal is
    initiated via :meth:`visit`, which just calls ``node.accept(self,
    env)`` — the node is responsible for selecting the right visit
    method.
    """

    def visit(self, node: Node, env: Env) -> Any:
        return node.accept(self, env)

    def visit_Number(self, node: Number, env: Env) -> Any:  # pragma: no cover
        raise NotImplementedError

    def visit_String(self, node: String, env: Env) -> Any:  # pragma: no cover
        raise NotImplementedError

    def visit_Symbol(self, node: Symbol, env: Env) -> Any:  # pragma: no cover
        raise NotImplementedError

    def visit_SList(self, node: SList, env: Env) -> Any:  # pragma: no cover
        raise NotImplementedError


_NIL: tuple[Any, ...] = ()  # the empty list doubles as "nil"


def _is_truthy(value: Any) -> bool:
    if value is False or value is None:
        return False
    if isinstance(value, tuple) and len(value) == 0:
        return False
    return True


def _format_value(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "nil"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, tuple):
        return "(" + " ".join(_format_value(v) for v in value) + ")"
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, Procedure):
        return f"#<procedure {value.name}>"
    if callable(value):
        return f"#<builtin {getattr(value, '__name__', 'proc')}>"
    return str(value)


class Evaluator(Visitor):
    """Tree-walking interpreter.

    Uses ``visit_SList`` to dispatch special forms vs. regular
    function calls.  Special forms take the *unevaluated* argument
    nodes so they can control their own evaluation strategy.
    """

    def __init__(self) -> None:
        self.special_forms: dict[str, Callable[[tuple[Node, ...], Env], Any]] = {
            "quote": self._f_quote,
            "if": self._f_if,
            "define": self._f_define,
            "set!": self._f_set,
            "lambda": self._f_lambda,
            "let": self._f_let,
            "begin": self._f_begin,
            "cond": self._f_cond,
            "and": self._f_and,
            "or": self._f_or,
        }

    def visit_Number(self, node: Number, env: Env) -> Any:
        return node.value

    def visit_String(self, node: String, env: Env) -> Any:
        return node.value

    def visit_Symbol(self, node: Symbol, env: Env) -> Any:
        if node.name == "true":
            return True
        if node.name == "false":
            return False
        if node.name == "nil":
            return _NIL
        return env.lookup(node.name)

    def visit_SList(self, node: SList, env: Env) -> Any:
        if not node.items:
            raise LispError("cannot evaluate empty combination ()")
        head, *rest = node.items
        if isinstance(head, Symbol) and head.name in self.special_forms:
            return self.special_forms[head.name](tuple(rest), env)
        fn = self.visit(head, env)
        args = [self.visit(arg, env) for arg in rest]
        if not callable(fn):
            raise LispError(f"not a procedure: {_format_value(fn)}")
        return fn(*args)

    def eval_body(self, body: tuple[Node, ...], env: Env) -> Any:
        result: Any = _NIL
        for node in body:
            result = self.visit(node, env)
        return result

    def run(self, program: list[Node], env: Env) -> Any:
        return self.eval_body(tuple(program), env)

    def _f_quote(self, args: tuple[Node, ...], env: Env) -> Any:
        if len(args) != 1:
            raise LispError("quote: expected exactly 1 argument")
        return _quote_to_value(args[0])

    def _f_if(self, args: tuple[Node, ...], env: Env) -> Any:
        if len(args) not in (2, 3):
            raise LispError("if: expected (if cond then [else])")
        cond = self.visit(args[0], env)
        if _is_truthy(cond):
            return self.visit(args[1], env)
        if len(args) == 3:
            return self.visit(args[2], env)
        return _NIL

    def _f_define(self, args: tuple[Node, ...], env: Env) -> Any:
        if not args:
            raise LispError("define: missing target")
        target = args[0]
        if isinstance(target, Symbol):
            if len(args) != 2:
                raise LispError("define: expected (define name value)")
            value = self.visit(args[1], env)
            if isinstance(value, Procedure) and value.name == "<lambda>":
                value = Procedure(
                    value.params, value.body, value.closure, value.evaluator,
                    name=target.name,
                )
            env.define(target.name, value)
            return _NIL
        if isinstance(target, SList) and target.items:
            # (define (name p1 p2 ...) body...)
            name_node = target.items[0]
            if not isinstance(name_node, Symbol):
                raise LispError("define: function name must be a symbol")
            params = _symbol_names(target.items[1:], "define")
            body = args[1:]
            if not body:
                raise LispError("define: function body is empty")
            proc = Procedure(params, body, env, self, name=name_node.name)
            env.define(name_node.name, proc)
            return _NIL
        raise LispError("define: invalid form")

    def _f_set(self, args: tuple[Node, ...], env: Env) -> Any:
        if len(args) != 2 or not isinstance(args[0], Symbol):
            raise LispError("set!: expected (set! name value)")
        env.assign(args[0].name, self.visit(args[1], env))
        return _NIL

    def _f_lambda(self, args: tuple[Node, ...], env: Env) -> Any:
        if len(args) < 2 or not isinstance(args[0], SList):
            raise LispError("lambda: expected (lambda (params...) body...)")
        params = _symbol_names(args[0].items, "lambda")
        return Procedure(params, args[1:], env, self)

    def _f_let(self, args: tuple[Node, ...], env: Env) -> Any:
        if len(args) < 2 or not isinstance(args[0], SList):
            raise LispError("let: expected (let ((name value)...) body...)")
        new_env = Env(parent=env)
        for binding in args[0].items:
            if (
                not isinstance(binding, SList)
                or len(binding.items) != 2
                or not isinstance(binding.items[0], Symbol)
            ):
                raise LispError("let: bindings must be (name value) pairs")
            name = binding.items[0].name
            new_env.define(name, self.visit(binding.items[1], env))
        return self.eval_body(args[1:], new_env)

    def _f_begin(self, args: tuple[Node, ...], env: Env) -> Any:
        return self.eval_body(args, env)

    def _f_cond(self, args: tuple[Node, ...], env: Env) -> Any:
        for clause in args:
            if not isinstance(clause, SList) or not clause.items:
                raise LispError("cond: each clause must be a non-empty list")
            test, *body = clause.items
            if isinstance(test, Symbol) and test.name == "else":
                return self.eval_body(tuple(body), env)
            if _is_truthy(self.visit(test, env)):
                if not body:
                    return self.visit(test, env)
                return self.eval_body(tuple(body), env)
        return _NIL

    def _f_and(self, args: tuple[Node, ...], env: Env) -> Any:
        result: Any = True
        for a in args:
            result = self.visit(a, env)
            if not _is_truthy(result):
                return result
        return result

    def _f_or(self, args: tuple[Node, ...], env: Env) -> Any:
        for a in args:
            result = self.visit(a, env)
            if _is_truthy(result):
                return result
        return False


def _symbol_names(nodes: tuple[Node, ...], where: str) -> tuple[str, ...]:
    names: list[str] = []
    for n in nodes:
        if not isinstance(n, Symbol):
            raise LispError(f"{where}: parameter list must contain only symbols")
        names.append(n.name)
    return tuple(names)


def _quote_to_value(node: Node) -> Any:
    """Turn an unevaluated AST node into a runtime quoted value.

    Numbers/strings become themselves; symbols become :class:`Symbol`
    instances; lists become tuples.
    """

    if isinstance(node, Number):
        return node.value
    if isinstance(node, String):
        return node.value
    if isinstance(node, Symbol):
        return node
    if isinstance(node, SList):
        return tuple(_quote_to_value(i) for i in node.items)
    raise LispError(f"cannot quote node: {node!r}")


class Formatter(Visitor):
    def visit_Number(self, node: Number, env: Env) -> str:
        return str(node.value)

    def visit_String(self, node: String, env: Env) -> str:
        return f'"{node.value}"'

    def visit_Symbol(self, node: Symbol, env: Env) -> str:
        return node.name

    def visit_SList(self, node: SList, env: Env) -> str:
        if (
            len(node.items) == 2
            and isinstance(node.items[0], Symbol)
            and node.items[0].name == "quote"
        ):
            return "'" + self.visit(node.items[1], env)
        return "(" + " ".join(self.visit(c, env) for c in node.items) + ")"


def format_program(program: list[Node]) -> str:
    fmt = Formatter()
    dummy = Env()
    return "\n".join(fmt.visit(n, dummy) for n in program)


def _variadic_sub(*args: Any) -> Any:
    if not args:
        raise LispError("-: expected at least 1 argument")
    if len(args) == 1:
        return -args[0]
    return reduce(operator.sub, args)


def _variadic_div(*args: Any) -> Any:
    if not args:
        raise LispError("/: expected at least 1 argument")
    if len(args) == 1:
        return 1 / args[0]
    return reduce(operator.truediv, args)


def _chained(op: Callable[[Any, Any], bool]) -> Callable[..., bool]:
    def _cmp(*args: Any) -> bool:
        if len(args) < 2:
            raise LispError("comparison needs at least 2 arguments")
        return all(op(a, b) for a, b in zip(args, args[1:]))

    return _cmp


def _cons(head: Any, tail: Any) -> tuple[Any, ...]:
    if not isinstance(tail, tuple):
        raise LispError("cons: second argument must be a list")
    return (head, *tail)


def _car(xs: Any) -> Any:
    if not isinstance(xs, tuple) or not xs:
        raise LispError("car: expected non-empty list")
    return xs[0]


def _cdr(xs: Any) -> Any:
    if not isinstance(xs, tuple) or not xs:
        raise LispError("cdr: expected non-empty list")
    return xs[1:]


def _length(xs: Any) -> int:
    if not isinstance(xs, tuple):
        raise LispError("length: expected a list")
    return len(xs)


def _print(*args: Any) -> Any:
    print(*(_format_value(a) for a in args))
    return _NIL


def _display(*args: Any) -> Any:
    for a in args:
        if isinstance(a, str):
            print(a, end="")
        else:
            print(_format_value(a), end="")
    return _NIL


def make_global_env() -> Env:
    env = Env()
    builtins: dict[str, Any] = {
        "+": lambda *a: sum(a) if a else 0,
        "-": _variadic_sub,
        "*": lambda *a: reduce(operator.mul, a, 1),
        "/": _variadic_div,
        "modulo": lambda a, b: a % b,
        "=": _chained(operator.eq),
        "<": _chained(operator.lt),
        ">": _chained(operator.gt),
        "<=": _chained(operator.le),
        ">=": _chained(operator.ge),
        "not": lambda x: not _is_truthy(x),
        "eq?": lambda a, b: a == b,
        "list": lambda *a: tuple(a),
        "cons": _cons,
        "car": _car,
        "cdr": _cdr,
        "null?": lambda x: isinstance(x, tuple) and len(x) == 0,
        "pair?": lambda x: isinstance(x, tuple) and len(x) > 0,
        "length": _length,
        "number?": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "string?": lambda x: isinstance(x, str),
        "symbol?": lambda x: isinstance(x, Symbol),
        "procedure?": lambda x: callable(x),
        "print": _print,
        "display": _display,
        "newline": lambda: (print(), _NIL)[1],
    }
    for name, fn in builtins.items():
        if hasattr(fn, "__name__"):
            try:
                fn.__name__ = name  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                pass
        env.define(name, fn)
    return env

def run(source: str, env: Env | None = None) -> Any:
    """Parse ``source`` and evaluate it, returning the last value."""

    parser = build_parser()
    program: list[Node] = parser.parse_text(source)
    evaluator = Evaluator()
    return evaluator.run(program, env or make_global_env())


SAMPLES: list[tuple[str, str]] = [
    (
        "arithmetic",
        "(+ 1 2 3 (* 4 5))",
    ),
    (
        "comparison + booleans",
        "(and (< 1 2 3) (not (= 1 2)))",
    ),
    (
        "if / let",
        """
        (let ((x 10) (y 3))
          (if (> x y) (- x y) (- y x)))
        """,
    ),
    (
        "factorial via recursion",
        """
        (define (fact n)
          (if (<= n 1) 1 (* n (fact (- n 1)))))
        (fact 6)
        """,
    ),
    (
        "higher-order map",
        """
        (define (map f xs)
          (if (null? xs)
              '()
              (cons (f (car xs)) (map f (cdr xs)))))
        (map (lambda (x) (* x x)) '(1 2 3 4 5))
        """,
    ),
    (
        "closures / counter",
        """
        (define (make-counter)
          (let ((n 0))
            (lambda ()
              (set! n (+ n 1))
              n)))
        (define tick (make-counter))
        (tick) (tick) (tick)
        """,
    ),
    (
        "cond",
        """
        (define (classify n)
          (cond ((< n 0) 'negative)
                ((= n 0) 'zero)
                (else    'positive)))
        (list (classify -5) (classify 0) (classify 7))
        """,
    ),
]


def main() -> None:
    parser = build_parser()
    for title, src in SAMPLES:
        program = parser.parse_text(src)
        pretty = format_program(program).strip()
        env = make_global_env()
        value = Evaluator().run(program, env)
        print(f"--- {title} ---")
        print(f"source : {pretty}")
        print(f"result : {_format_value(value)}")
        print()


if __name__ == "__main__":
    main()
