"""
  A simple (naive) LL(1) parser.
  Copyright (C) 2016 Victor C. Martins (dxhj)
  
  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
  
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  
  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

#!/usr/bin/python
# -*- coding: UTF-8 -*-

class PredictiveParser(object):
	def is_terminal(self, sym):
		if not sym or sym[0].isupper():
			return 0
		return 1

	def is_nonterminal(self, sym):
		if not sym or not sym[0].isupper():
			return 0
		return 1

	def __init__(self, start, grammar):
		self.start = start
		self.grammar = grammar
		self.terminals = set()
		self.nonterminals = set()
		self.null_dict = self.gen_nullable()
		self.first_dict = self.gen_first()
		self.follow_dict = self.gen_follow()
		self.table = self.gen_table()

	def match(self, seq):
		seq.append('$')
		si = 0
		stack = ['$', self.start]
		top = self.start
		while top != '$':
			if top == seq[si]:
				si = si + 1
				stack.pop()
			elif (self.is_terminal(top)):
				return False
			else:
				try:
					prod = self.table[top, seq[si]]
					stack.pop()
					if prod != [""]:
						stack.extend(reversed(prod))
				except KeyError:
					return False
			top = stack[-1]
		return True

	def verbose_match(self, seq, display_stack=False):
		seq.append('$')
		si = 0
		stack = ['$', self.start]
		top = self.start
		while top != '$':
			if display_stack:
				print "Stack:", stack
			if top == seq[si]:
				si = si + 1
				print "** Action: match `{0}`".format(top)
				stack.pop()
			elif (self.is_terminal(top)):
				return False
			else:
				try:
					prod = self.table[top, seq[si]]
					stack.pop()
					if prod == [""]:
						print "** Action: derive {0} on `{1}` to: ε".format(top, seq[si])
					else:
						print "** Action: derive {0} on `{1}` to: {2}".format(top, seq[si], " ".join(prod))
						stack.extend(reversed(prod))
				except KeyError:
					print "ERROR: Not able to find derivation of {0} on `{1}`".format(top, seq[si])
					return False
			top = stack[-1]
		return True

	def gen_table(self):
		table = {}
		for head, prods in self.grammar.iteritems():
			for prod in prods:
				first_set = self.first(prod)
				for terminal in first_set - set([""]):
					table[head, terminal] = prod
				if "" in first_set:
					for terminal in self.follow_dict[head]:
						table[head, terminal] = prod
					if '$' in self.follow_dict[head]:
						table[head, '$'] = prod
		return table

	def print_table(self):
		for nonterminal in self.nonterminals:
			for terminal in self.terminals.union(set(['$'])):
				try:
					prod = self.table[nonterminal, terminal]
					print "(" + nonterminal + ", " + terminal + ") =",
					print prod
				except KeyError:
					pass

	def gen_nullable(self):
		null_dict = {"": True}
		for head, prods in self.grammar.iteritems():
			null_dict[head] = False
			self.nonterminals.add(head)
			for prod in prods:
				for symbol in prod:
					if self.is_terminal(symbol):
						null_dict[symbol] = False
						self.terminals.add(symbol)
					elif not symbol:
						null_dict[head] = True
		while True:
			changes = 0
			for head, prods in self.grammar.iteritems():
				for prod in prods:
					all_nullable = True
					for symbol in prod:
						if not null_dict[symbol]:
							all_nullable = False
							break
					if all_nullable and not (head in null_dict and null_dict[head]):
						null_dict[head] = True
						changes = changes + 1
			if changes == 0:
				return null_dict		

	def nullable(self, symbols):
		if not symbols:
			return True
		elif not self.null_dict[symbols[0]]:
			return False
		return self.nullable(symbols[1:])

	def gen_first(self):
		first_dict = {}
		for head, prods in self.grammar.iteritems():
			first_dict[head] = set()
			for prod in prods:
				for symbol in prod:
					if self.is_terminal(symbol):
						first_dict[symbol] = set([symbol])
		while True:
			changes = first_dict.copy()
			for head, prods in self.grammar.iteritems():
				for prod in prods:
					if not prod[0]:
						first_dict[head] = first_dict[head].union(set([""]))
					else:
						first_dict[head] = first_dict[head].union(first_dict[prod[0]])
					for i in xrange(1, len(prod)):
						if self.nullable(prod[:i]):
							if not prod[0]:
								first_dict[head] = first_dict[head].union(set([""]))
							else:
								first_dict[head] = first_dict[head].union(first_dict[prod[0]])
			if changes == first_dict:
				return first_dict

	def first(self, symbols):
		if not symbols:
			return set()
		if "" in symbols:
			return set([""])
		if not self.null_dict[symbols[0]]:
			return self.first_dict[symbols[0]]
		return self.first_dict[symbols[0]].union(self.first(symbols[1:]))

	def gen_follow(self):
		follow_dict = {}
		for head in self.grammar:
			if head == self.start:
				follow_dict[self.start] = set(["$"])
			else:
				follow_dict[head] = set()
		while True:
			changes = follow_dict.copy()
			for head, prods in self.grammar.iteritems():
				for prod in prods:

					for i in xrange(len(prod)-1):
						if self.is_nonterminal(prod[i]):
							follow_dict[prod[i]] = follow_dict[prod[i]].union(self.first(prod[i+1:]) - set([""]))	

					for i in reversed(xrange(len(prod))):
						if self.is_nonterminal(prod[i]) and self.nullable(prod[i+1:]):
							follow_dict[prod[i]] = follow_dict[prod[i]].union(follow_dict[head])

			if changes == follow_dict:
				return follow_dict	
