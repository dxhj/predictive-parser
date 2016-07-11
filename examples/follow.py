from predictive import PredictiveParser

parser = PredictiveParser("E", {
	"E": [["T", "E'"]],
	"E'": [["+", "T", "E'"], [""]],
	"T": [["F", "T'"]],
	"T'": [["*", "F", "T'"], [""]],
	"F": [["(", "E", ")"], ["id"]]
})

for nonterminal, symbols in parser.follow_dict.iteritems():
	print nonterminal, symbols