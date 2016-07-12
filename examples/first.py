from predictive import PredictiveParser

parser = PredictiveParser("E", {
	"E": [["T", "E'"]],
	"E'": [["+", "T", "E'"], [""]],
	"T": [["F", "T'"]],
	"T'": [["*", "F", "T'"], [""]],
	"F": [["(", "E", ")"], ["id"]]
})

# Print first set of terminals.
for symbol, items in parser.first_dict.iteritems():
	if symbol in parser.terminals:
		print symbol, items
"""
	) set([')'])
	( set(['('])
	* set(['*'])
	id set(['id'])
	+ set(['+'])
"""
		
# Print first set of nonterminals.
for symbol, items in parser.first_dict.iteritems():
	if symbol in parser.nonterminals:
		print symbol, items
"""
	E set(['(', 'id'])
	F set(['(', 'id'])
	E' set(['', '+'])
	T set(['(', 'id'])
	T' set(['', '*'])
"""
