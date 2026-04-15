from predictive import EPSILON, PredictiveParser

parser = PredictiveParser("E", {
    "E": [["T", "Ep"]],
    "Ep": [["+", "T", "Ep"], [EPSILON]],
    "T": [["F", "Tp"]],
    "Tp": [["*", "F", "Tp"], [EPSILON]],
    "F": [["(", "E", ")"], ["id"]],
})

for nonterminal, symbols in parser.follow_dict.items():
    print(nonterminal, symbols)
"""
  Tp {'$', ')', '+'}
  Ep {')', '$'}
  E {')', '$'}
  T {')', '+', '$'}
  F {'$', ')', '+', '*'}
"""
