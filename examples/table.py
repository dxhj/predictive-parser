from predictive import EPSILON, PredictiveParser

parser0 = PredictiveParser("S", {
    "S": [["0", "Sp"]],
    "Sp": [["S", "1"], ["1"]],
})

parser0.print_table()
"""
  (S, 0) = ['0', 'Sp']
  (Sp, 1) = ['1']
  (Sp, 0) = ['S', '1']
"""

parser1 = PredictiveParser("E", {
    "E": [["T", "Ep"]],
    "Ep": [["+", "T", "Ep"], [EPSILON]],
    "T": [["F", "Tp"]],
    "Tp": [["*", "F", "Tp"], [EPSILON]],
    "F": [["(", "E", ")"], ["id"]],
})

parser1.print_table()
"""
  (Tp, $) = ['']
  (Tp, )) = ['']
  (Tp, +) = ['']
  (Tp, *) = ['*', 'F', 'Tp']
  (Ep, $) = ['']
  (Ep, )) = ['']
  (Ep, +) = ['+', 'T', 'Ep']
  (E, () = ['T', 'Ep']
  (E, id) = ['T', 'Ep']
  (T, () = ['F', 'Tp']
  (T, id) = ['F', 'Tp']
  (F, () = ['(', 'E', ')']
  (F, id) = ['id']
"""
