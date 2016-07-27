from predictive import PredictiveParser

parser = PredictiveParser("E", {
	"E": [["T", "E'"]],
	"E'": [["+", "T", "E'"], [""]],
	"T": [["F", "T'"]],
	"T'": [["*", "F", "T'"], [""]],
	"F": [["(", "E", ")"], ["id"]]
})

# Print first set of terminals.
for terminal in parser.terminals:
	print terminal, parser.first_dict[terminal]
"""
	) set([')'])
	( set(['('])
	+ set(['+'])
	* set(['*'])
	id set(['id'])
"""
		
# Print first set of nonterminals.
for nonterminal in parser.nonterminals:
	print nonterminal, parser.first_dict[nonterminal]
"""
	T' set(['', '*'])
	E' set(['', '+'])
	E set(['(', 'id'])
	T set(['(', 'id'])
	F set(['(', 'id'])
"""
