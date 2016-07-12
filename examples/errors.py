from predictive import PredictiveParser

parser = PredictiveParser("S", {
	"S": [["0", "S'"]],
	"S'": [["S", "1"], ["1"]]
})

"""
  Using .verbose_match(), when the parser tries to access an entry that it's not in the table
  it shows the attempt to retrive a production from table[nonterminal, terminal]:
"""
if parser.verbose_match(["0", "0"]):
	print "ACCEPT"
else:
	print "REJECT"
"""
  outputs: 
  ** Action: derive S on `0` to: 0 S'
  ** Action: match `0`
  ** Action: derive S' on `0` to: S 1
  ** Action: derive S on `0` to: 0 S'
  ** Action: match `0`
  ERROR: Not able to find derivation of S' on `$`
  REJECT
"""

# The following wrong input doesn't make .verbose_match() to generate an error, but it's still not accepted:
if parser.verbose_match(["0", "0", "1"]):
	print "ACCEPT"
else:
	print "REJECT"
"""
  outputs:
  ** Action: derive S on `0` to: 0 S'
  ** Action: match `0`
  ** Action: derive S' on `0` to: S 1
  ** Action: derive S on `0` to: 0 S'
  ** Action: match `0`
  ** Action: derive S' on `1` to: 1
  ** Action: match `1`
  REJECT
"""
