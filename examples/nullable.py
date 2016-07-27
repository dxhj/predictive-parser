from predictive import PredictiveParser

parser = PredictiveParser("E", {
	"E": [["T", "E'"]],
	"E'": [["+", "T", "E'"], [""]],
	"T": [["F", "T'"]],
	"T'": [["*", "F", "T'"], [""]],
	"F": [["(", "E", ")"], ["id"]]
})

for terminal in parser.terminals:
	print terminal + ": " + str(parser.null_dict[terminal])
"""
	): False
	(: False
	+: False
	*: False
	id: False
"""

for nonterminal in parser.nonterminals:
	print nonterminal + ": " + str(parser.null_dict[nonterminal])
"""
	T': True
	E': True
	E: False
	T: False
	F: False
"""
