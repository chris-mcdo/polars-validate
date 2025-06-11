# polars_validate: Polars DataFrame validation using type hints

Simple DataFrame validation, based on type hints.

```
from typing import Annotated

import polars as pl

from polars_validate import (
    THIS,
    ContainsPattern,
    FrameValidators,
    IntegerType,
    IsBetween,
    IsIn,
    IsNotNull,
    UniqueTogether,
    validate,
)

tips = pl.DataFrame(
    {
        "restaurant": [1, 1, 1, 2],
        "table": [1, 2, 3, 1],
        "bill": [16.99, 10.34, 21.01, 23.68],
        "tip": [1.01, 1.66, 3.5, None],
        "sex": ["Female", "Male", None, "Male"],
        "smoker": [False, True, True, False],
        "time": ["45 min", "30 mins", "60 min", "50 min"],
    }
)


class TipsSchema:
    restaurant: Annotated[IntegerType, IsNotNull()]
    table: Annotated[IntegerType, IsNotNull()]
    bill: Annotated[pl.Float64, IsNotNull(), IsBetween(0.0, 50.0, closed="right")]
    tip: pl.Float64
    sex: Annotated[pl.String, IsNotNull(), IsIn(("Female", "Male"))]
    smoker: Annotated[pl.Boolean, IsNotNull()]
    time: Annotated[
        pl.String,
        ContainsPattern("^\\d+ min$"),
        THIS.str.strip_suffix(" min").cast(pl.Int64, strict=False) < 120,
    ]

    dataframe: FrameValidators = (
        UniqueTogether(("restaurant", "table")),
        pl.col("bill") > pl.col("tip"),
    )


validate(TipsSchema, tips, eager=False)
#> polars_validate.base.ValidationError: Validation failed with 2 errors (16 passed):
#> ❌ 'sex': 'not null' check failed at offsets: [2]
#> ❌ 'time': 'pattern ^\d+ min$' check failed at offsets: [1]
```

## Installation

`pip install git+https://github.com/chris-mcdo/polars-validate`

## Features

Validate using built-in validation types, polars expressions, or arbitrary functions.

In-built validation:
* `IsNotNull`: check for missing values
* `IsIn`: check for set membership
* `IsBetween`: check values lie within an interval
* `ContainsPattern`: check a string contains / matches a regex pattern
* `TypeValidator`: check type
* `UniqueTogether`: check some columns uniquely identify rows

For inspiration, a few examples of how polars expressions can be used for validation:

```
# THIS represents the the current Series / column.
from polars_validate import THIS

# series-based validation
is_even = (THIS % 2) == 0
is_in_title_case = THIS.str.title() == THIS
starts_with_foo = THIS.str.starts_with("foo")
is_close_to_mean = (THIS - THIS.mean()).abs() < 5.0
is_unique = THIS.is_unique()
is_short_string = THIS.str.len() < 10

# dataframe-based validation
bounded = pl.col("col_a").is_between("col_b", "col_c")
at_least_one = pl.any_horizontal("a", "b", "c")
```

Arbitrary custom validation is also supported:

```
def is_valid_index(s: pl.Series) -> bool:
    return s.is_sorted() and s[0] == 1


def smokers_tip_more(d: pl.DataFrame):
    # arbitrary logic ...


class TipsSchema:
    restaurant: Annotated[IntegerType, IsNotNull(), SeriesCallableValidator(is_valid_index, "valid index")]
    # ...

    dataframe: FrameValidators = (
        # ...
        CallableValidator(smokers_tip_more, "smokers tip more"),
    )
```

## User Guide

Define validation for individual Series (or DataFrame columns) using type annotations as shown above.

E.g. for series:

```
# simple schema - just validate type
SimpleSeriesSchema = pl.Float32

# add more complex validation using type metadata
StrictSeriesSchema = Annotated[pl.Float32, IsNotNull(), THIS.sqrt().round().mod(7).eq(0), ...]

validate_series(StrictSeriesSchema, my_series)
#> ...
```

To validate DataFrames, combine Series type annotations in a class as shown above.
To add validation which applies to the whole dataframe, add fields with the `FrameValidators`
annotation.

Internally, type annotations and metadata are translated into a sequence of `Validator` objects.
You can just use these objects directly if you want.

## License

Licensed under the MIT License.
