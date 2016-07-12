from predictive import PredictiveParser

parser0 = PredictiveParser("S", {
	"S": [["0", "S'"]],
	"S'": [["S", "1"], ["1"]]
})

parser0.print_table()
"""
  (S, 0) = ['0', "S'"]
  (S', 1) = ['1']
  (S', 0) = ['S', '1']
"""

parser1 = PredictiveParser("E", {
	"E": [["T", "E'"]],
	"E'": [["+", "T", "E'"], [""]],
	"T": [["F", "T'"]],
	"T'": [["*", "F", "T'"], [""]],
	"F": [["(", "E", ")"], ["id"]]
})

parser1.print_table()
"""
  (T', $) = ['']
  (T', )) = ['']
  (T', +) = ['']
  (T', *) = ['*', 'F', "T'"]
  (E', $) = ['']
  (E', )) = ['']
  (E', +) = ['+', 'T', "E'"]
  (E, () = ['T', "E'"]
  (E, id) = ['T', "E'"]
  (T, () = ['F', "T'"]
  (T, id) = ['F', "T'"]
  (F, () = ['(', 'E', ')']
  (F, id) = ['id']
"""
