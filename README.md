# predictive-parser
A simple (naive) LL(1) parser in Python.

* You can send pull requests, I'd appreciate.

## Basic usage
1. The first parameter receives the start symbol, the second receives the production itself:
  ```
  parser = PredictiveParser("S", {
    # Each nonterminal contains a list of productions:
    # S -> hello
    "S": [["hello"]]
  })
  ```

2. Empty productions are represented by [""]:
  ```
  parser = PredictiveParser("S", {
    # S -> hello T
  	"S": [["hello", "T"]],
  	# T -> + | hello | ε
  	"T": [["+"], ["hello"], [""]]
  })
  ```

3. A complete usage is found in [examples](https://github.com/dxhj/predictive-parser/tree/master/examples).
