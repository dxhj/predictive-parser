from predictive import EPSILON, PredictiveParser

parser = PredictiveParser("E", {
    "E": [["T", "Ep"]],
    "Ep": [["+", "T", "Ep"], [EPSILON]],
    "T": [["F", "Tp"]],
    "Tp": [["*", "F", "Tp"], [EPSILON]],
    "F": [["(", "E", ")"], ["id"]],
})

for terminal in parser.terminals:
    print(f"{terminal}: {parser.null_dict[terminal]}")
"""
  ): False
  (: False
  +: False
  *: False
  id: False
"""

for nonterminal in parser.nonterminals:
    print(f"{nonterminal}: {parser.null_dict[nonterminal]}")
"""
  Tp: True
  Ep: True
  E: False
  T: False
  F: False
"""
