from predictive import EPSILON, PredictiveParser

parser = PredictiveParser("E", {
    "E": [["T", "Ep"]],
    "Ep": [["+", "T", "Ep"], [EPSILON]],
    "T": [["F", "Tp"]],
    "Tp": [["*", "F", "Tp"], [EPSILON]],
    "F": [["(", "E", ")"], ["id"]],
})

if parser.match(["id", "+", "id"]):
    print("ACCEPT")
else:
    print("REJECT")

parser.verbose_match(["id", "+", "id"])
"""
 .verbose_match() outputs the sequence of derivation steps:
  ** Action: derive E on `id` to: T Ep
  ** Action: derive T on `id` to: F Tp
  ** Action: derive F on `id` to: id
  ** Action: match `id`
  ** Action: derive Tp on `+` to: ε
  ** Action: derive Ep on `+` to: + T Ep
  ** Action: match `+`
  ** Action: derive T on `id` to: F Tp
  ** Action: derive F on `id` to: id
  ** Action: match `id`
  ** Action: derive Tp on `$` to: ε
  ** Action: derive Ep on `$` to: ε
"""

parser.verbose_match(["id", "+", "id"], display_stack=True)
"""
 With display_stack=True, it displays the stack at each step:
  Stack: ['$', 'E']
  ** Action: derive E on `id` to: T Ep
  Stack: ['$', 'Ep', 'T']
  ** Action: derive T on `id` to: F Tp
  Stack: ['$', 'Ep', 'Tp', 'F']
  ** Action: derive F on `id` to: id
  Stack: ['$', 'Ep', 'Tp', 'id']
  ** Action: match `id`
  Stack: ['$', 'Ep', 'Tp']
  ** Action: derive Tp on `+` to: ε
  Stack: ['$', 'Ep']
  ** Action: derive Ep on `+` to: + T Ep
  Stack: ['$', 'Ep', 'T', '+']
  ** Action: match `+`
  Stack: ['$', 'Ep', 'T']
  ** Action: derive T on `id` to: F Tp
  Stack: ['$', 'Ep', 'Tp', 'F']
  ** Action: derive F on `id` to: id
  Stack: ['$', 'Ep', 'Tp', 'id']
  ** Action: match `id`
  Stack: ['$', 'Ep', 'Tp']
  ** Action: derive Tp on `$` to: ε
  Stack: ['$', 'Ep']
  ** Action: derive Ep on `$` to: ε
"""
