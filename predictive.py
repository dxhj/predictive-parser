#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""Backward-compatibility shim for the legacy ``predictive`` module.

The implementation has moved to the :mod:`predictive_parser` package.  This
module re-exports the classic names so that existing code — and the test
suite — keeps working without changes.

Copyright (C) 2016 Victor C. Martins (dxhj)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from predictive_parser import (
    EPSILON,
    MatchResult,
    PredictiveParser,
    SimpleToken,
    TokenLike,
    __version__,
)

__all__ = [
    "EPSILON",
    "MatchResult",
    "PredictiveParser",
    "SimpleToken",
    "TokenLike",
    "__version__",
]
