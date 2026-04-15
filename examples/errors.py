from predictive import PredictiveParser

parser = PredictiveParser("S", {
    "S": [["0", "Sp"]],
    "Sp": [["S", "1"], ["1"]],
})

"""
Using .verbose_match(), when the parser tries to access an entry that is not
in the table it shows the attempt to retrieve a production from
table[nonterminal, terminal]:
"""
if parser.verbose_match(["0", "0"]):
    print("ACCEPT")
else:
    print("REJECT")
"""
  ** Action: derive S on `0` to: 0 Sp
  ** Action: match `0`
  ** Action: derive Sp on `0` to: S 1
  ** Action: derive S on `0` to: 0 Sp
  ** Action: match `0`
  ERROR: Not able to find derivation of Sp on `$`
  REJECT
"""

if parser.verbose_match(["0", "0", "1"]):
    print("ACCEPT")
else:
    print("REJECT")
"""
  ** Action: derive S on `0` to: 0 Sp
  ** Action: match `0`
  ** Action: derive Sp on `0` to: S 1
  ** Action: derive S on `0` to: 0 Sp
  ** Action: match `0`
  ** Action: derive Sp on `1` to: 1
  ** Action: match `1`
  REJECT
"""

"""
Using .detailed_match() returns a MatchResult with diagnostic info
(position in the input, expected tokens, and actual token):
"""
result = parser.detailed_match(["0", "0"])
print(result)
"""
  MatchResult(success=False, position=2, expected={'1'}, got='$')
"""

result = parser.detailed_match(["0", "0", "1"])
print(result)
"""
  MatchResult(success=False, position=3, expected={'$'}, got='1')
"""
