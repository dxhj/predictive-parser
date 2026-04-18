"""Grammar transformations: EBNF desugaring, left-factoring,
left-recursion elimination.

These transformations turn non-LL(1) friendly grammars into equivalent
LL(1) grammars by introducing fresh nonterminals.  They operate on the
plain ``dict[str, list[list[str]]]`` representation so they can be used
independently of the DSL loader.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .sets import EPSILON

EmitFn = Callable[[str, list[str]], None]
FreshFn = Callable[[str], str]


# ---------------------------------------------------------------------------
# EBNF desugaring
# ---------------------------------------------------------------------------


def desugar_ebnf(
    nodes: list[Any],
    head: str,
    emit: EmitFn,
    fresh: FreshFn,
) -> list[str]:
    """Lower a list of ``_EBNFNode`` into a plain symbol sequence.

    New helper nonterminals are created via ``fresh`` and emitted via
    ``emit``.  Returns the symbol list for the enclosing production.
    """

    out: list[str] = []
    for node in nodes:
        out.extend(_desugar(node, head, emit, fresh))
    if not out:
        return [EPSILON]
    return out


def _desugar(
    node: Any,
    head: str,
    emit: EmitFn,
    fresh: FreshFn,
) -> list[str]:
    kind = node.kind
    if kind == "sym" or kind == "term":
        return [str(node.value)]
    if kind == "eps":
        return []
    if kind == "group":
        # A group with multiple alternatives becomes a fresh nonterminal
        # unless it has a single alternative and no postfix — in which
        # case we can inline.
        if len(node.children) == 1 and all(
            c.kind in ("sym", "term", "eps") for c in node.children[0].children
        ):
            return desugar_ebnf(node.children[0].children, head, emit, fresh)
        name = fresh(head)
        for alt in node.children:
            body = desugar_ebnf(alt.children, name, emit, fresh)
            emit(name, body)
        return [name]
    if kind == "seq":
        return desugar_ebnf(node.children, head, emit, fresh)
    if kind == "opt":
        child = node.children[0]
        name = fresh(head)
        body = desugar_ebnf([child], name, emit, fresh)
        emit(name, body)
        emit(name, [EPSILON])
        return [name]
    if kind == "star":
        child = node.children[0]
        name = fresh(head)
        child_syms = desugar_ebnf([child], name, emit, fresh)
        emit(name, list(child_syms) + [name])
        emit(name, [EPSILON])
        return [name]
    if kind == "plus":
        child = node.children[0]
        outer = fresh(head)
        inner = fresh(head)
        child_syms = desugar_ebnf([child], outer, emit, fresh)
        emit(outer, list(child_syms) + [inner])
        emit(inner, list(child_syms) + [inner])
        emit(inner, [EPSILON])
        return [outer]
    raise ValueError(f"unknown EBNF node kind: {kind}")


# ---------------------------------------------------------------------------
# Left-recursion elimination (immediate)
# ---------------------------------------------------------------------------


def eliminate_left_recursion(
    grammar: dict[str, list[list[str]]],
) -> dict[str, list[list[str]]]:
    """Remove immediate left-recursion using the standard textbook transform.

    Indirect left-recursion is first converted to immediate form via the
    Paull algorithm.  Productions are preserved in their original order
    whenever possible to keep deterministic behavior.
    """

    order = list(grammar.keys())
    rules = {k: [list(p) for p in v] for k, v in grammar.items()}

    for i, ai in enumerate(order):
        for j in range(i):
            aj = order[j]
            new_prods: list[list[str]] = []
            for prod in rules[ai]:
                if prod and prod[0] == aj:
                    tail = prod[1:]
                    for aj_prod in rules[aj]:
                        if aj_prod == [EPSILON]:
                            new_prods.append(list(tail) or [EPSILON])
                        else:
                            new_prods.append(list(aj_prod) + list(tail))
                else:
                    new_prods.append(prod)
            rules[ai] = new_prods
        rules[ai] = _remove_immediate_left_recursion(ai, rules[ai], rules)

    return rules


def _remove_immediate_left_recursion(
    head: str,
    prods: list[list[str]],
    rules: dict[str, list[list[str]]],
) -> list[list[str]]:
    alpha: list[list[str]] = []
    beta: list[list[str]] = []
    for prod in prods:
        if prod and prod[0] == head:
            alpha.append(prod[1:])
        else:
            beta.append(prod)
    if not alpha:
        return prods
    tail = f"{head}__lr"
    while tail in rules:
        tail += "_"
    new_head: list[list[str]] = []
    for b in beta:
        if b == [EPSILON]:
            new_head.append([tail])
        else:
            new_head.append(list(b) + [tail])
    if not beta:
        new_head.append([tail])
    new_tail: list[list[str]] = []
    for a in alpha:
        new_tail.append(list(a) + [tail])
    new_tail.append([EPSILON])
    rules[tail] = new_tail
    return new_head


# ---------------------------------------------------------------------------
# Left-factoring (common-prefix extraction)
# ---------------------------------------------------------------------------


def left_factor(
    grammar: dict[str, list[list[str]]],
) -> dict[str, list[list[str]]]:
    """Factor out common left prefixes across productions of each head.

    Iterates until no more common prefixes exist (multi-pass).  Introduces
    fresh nonterminals of the form ``<head>__lf``.
    """

    rules = {k: [list(p) for p in v] for k, v in grammar.items()}
    changed = True
    fresh_counter = 0
    while changed:
        changed = False
        for head in list(rules.keys()):
            prods = rules[head]
            groups: dict[str, list[list[str]]] = {}
            for prod in prods:
                first = prod[0] if prod and prod[0] != EPSILON else EPSILON
                groups.setdefault(first, []).append(prod)
            new_prods: list[list[str]] = []
            head_changed = False
            for first, bucket in groups.items():
                if first == EPSILON or len(bucket) == 1:
                    new_prods.extend(bucket)
                    continue
                common = _longest_common_prefix(bucket)
                if len(common) < 1:
                    new_prods.extend(bucket)
                    continue
                fresh_counter += 1
                new_name = f"{head}__lf{fresh_counter}"
                while new_name in rules:
                    fresh_counter += 1
                    new_name = f"{head}__lf{fresh_counter}"
                new_prods.append(list(common) + [new_name])
                rules[new_name] = []
                for prod in bucket:
                    rem = prod[len(common):]
                    if not rem:
                        rules[new_name].append([EPSILON])
                    else:
                        rules[new_name].append(rem)
                head_changed = True
            if head_changed:
                rules[head] = new_prods
                changed = True
    return rules


def _longest_common_prefix(bucket: list[list[str]]) -> list[str]:
    if not bucket:
        return []
    prefix = list(bucket[0])
    for prod in bucket[1:]:
        i = 0
        while i < len(prefix) and i < len(prod) and prefix[i] == prod[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix


__all__ = [
    "desugar_ebnf",
    "eliminate_left_recursion",
    "left_factor",
]
