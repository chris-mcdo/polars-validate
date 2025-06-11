from typing import Literal

import polars as pl

ClosedInterval = Literal["left", "right", "both", "none"]
OFFSET = "offset"
"""Offset column name for reporting invalid items in a Series or DataFrame."""
THIS = pl.first()
"""An expression representing the current Series."""
_IS_VALID = "__is_valid"
