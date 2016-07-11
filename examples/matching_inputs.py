from predictive import PredictiveParser

parser = PredictiveParser("E", {
	"E": [["T", "E'"]],
	"E'": [["+", "T", "E'"], [""]],
	"T": [["F", "T'"]],
	"T'": [["*", "F", "T'"], [""]],
	"F": [["(", "E", ")"], ["id"]]
})

if parser.match(["id", "+", "id"]):
	print "ACCEPT"
else:
	print "REJECT"

parser.verbose_match(["id", "+", "id"])
"""
 .verbose_match() outputs the sequence of derivation steps:
	** Action: reduce E on `id` to: T E'
	** Action: reduce T on `id` to: F T'
	** Action: reduce F on `id` to: id
	** Action: match `id`
	** Action: reduce T' on `+` to: ε
	** Action: reduce E' on `+` to: + T E'
	** Action: match `+`
	** Action: reduce T on `id` to: F T'
	** Action: reduce F on `id` to: id
	** Action: match `id`
	** Action: reduce T' on `$` to: ε
	** Action: reduce E' on `$` to: ε
"""

parser.verbose_match(["id", "+", "id"], True)
"""
 If the second param is True, it displays the stack at each step:
	Stack: ['$', 'E']
	** Action: reduce E on `id` to: T E'
	Stack: ['$', "E'", 'T']
	** Action: reduce T on `id` to: F T'
	Stack: ['$', "E'", "T'", 'F']
	** Action: reduce F on `id` to: id
	Stack: ['$', "E'", "T'", 'id']
	** Action: match `id`
	Stack: ['$', "E'", "T'"]
	** Action: reduce T' on `+` to: ε
	Stack: ['$', "E'"]
	** Action: reduce E' on `+` to: + T E'
	Stack: ['$', "E'", 'T', '+']
	** Action: match `+`
	Stack: ['$', "E'", 'T']
	** Action: reduce T on `id` to: F T'
	Stack: ['$', "E'", "T'", 'F']
	** Action: reduce F on `id` to: id
	Stack: ['$', "E'", "T'", 'id']
	** Action: match `id`
	Stack: ['$', "E'", "T'"]
	** Action: reduce T' on `$` to: ε
	Stack: ['$', "E'"]
	** Action: reduce E' on `$` to: ε
"""
