from predictive import PredictiveParser

parser = PredictiveParser("E", {
	"E": [["T", "E'"]],
	"E'": [["+", "T", "E'"], [""]],
	"T": [["F", "T'"]],
	"T'": [["*", "F", "T'"], [""]],
	"F": [["(", "E", ")"], ["id"]]
})

for symbol, nullable in parser.null_dict.iteritems():
	if symbol in parser.terminals:
		print symbol + ": " + str(nullable)
"""
	): False
	(: False
	*: False
	id: False
	+: False
"""

for symbol, nullable in parser.null_dict.iteritems():
	if symbol in parser.nonterminals:
		print symbol + ": " + str(nullable)
"""
	E: False
	F: False
	E': True
	T: False
	T': True
"""
