from predictive import EPSILON, PredictiveParser

parser = PredictiveParser("E", {
    "E": [["T", "Ep"]],
    "Ep": [["+", "T", "Ep"], [EPSILON]],
    "T": [["F", "Tp"]],
    "Tp": [["*", "F", "Tp"], [EPSILON]],
    "F": [["(", "E", ")"], ["id"]],
})

for terminal in parser.terminals:
    print(terminal, parser.first_dict[terminal])
"""
  ) {')'}
  ( {'('}
  + {'+'}
  * {'*'}
  id {'id'}
"""

for nonterminal in parser.nonterminals:
    print(nonterminal, parser.first_dict[nonterminal])
"""
  Tp {'', '*'}
  Ep {'', '+'}
  E {'(', 'id'}
  T {'(', 'id'}
  F {'(', 'id'}
"""
