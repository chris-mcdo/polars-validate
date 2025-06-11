"""Series validators."""

import reprlib
from typing import Callable, Optional, Union

import polars as pl
from polars.datatypes import DataTypeClass

from polars_validate.base import ValidationError
from polars_validate.constants import _IS_VALID, OFFSET, THIS, ClosedInterval


class SeriesValidator:
    """Validate a Polars Series, or column of a DataFrame."""

    def __call__(self, data: pl.Series) -> None:
        """Validate a Series.

        Args:
            series (pl.Series): The Series to validate.

        Raises:
            ValidationError: If the Series fails validation.
        """
        pass


class SeriesValidatorGroup(SeriesValidator):
    """Run a sequence of Series validators."""

    def __init__(self, validators: tuple[SeriesValidator, ...], eager: bool = False):
        self.validators = validators
        self.eager = eager

    def __call__(self, data: pl.Series) -> None:
        errors = []
        for validator in self.validators:
            try:
                validator(data)
            except ValidationError as e:
                if self.eager:
                    raise
                errors.append(e.message)

        if len(errors) > 0:
            num_success = len(self.validators) - len(errors)
            errors_str = "\n".join(errors)
            raise ValidationError(
                f"Validation on {data.name} failed with {len(errors)} errors"
                f" ({num_success} passed):\n{errors_str}",
            )


class SeriesExpressionValidator(SeriesValidator):
    """Validate a Series based on an arbitrary expression."""

    def __init__(self, expression: pl.Expr, description: Optional[str] = None):
        self.description = description
        self.expression = expression

    def __call__(self, data: pl.Series):
        invalid_items = (
            data.to_frame()
            .with_columns(self.expression.alias(_IS_VALID))
            .with_row_index(OFFSET)
            .filter(pl.col(_IS_VALID).eq(False))
            .drop(_IS_VALID)
        )
        if not invalid_items.is_empty():
            offsets = invalid_items.get_column(OFFSET).to_list()
            offsets_str = reprlib.repr(offsets)
            description_str = (
                f" '{self.description}'" if self.description is not None else ""
            )
            raise ValidationError(
                f"❌ '{data.name}':{description_str} check failed at offsets: {offsets_str}"
            )


class SeriesCallableValidator(SeriesValidator):
    """Validate a Series based on an arbitrary `Callable[[pl.Series], bool]`."""

    def __init__(
        self, func: Callable[[pl.Series], bool], description: Optional[str] = None
    ):
        self.func = func
        self.description = description

    def __call__(self, data: pl.Series):
        result = self.func(data)
        if not isinstance(result, bool):
            raise TypeError(
                "Return value of SeriesCallableValidator function must be boolean,"
                f" got {type(result)}"
            )

        description_str = (
            f" '{self.description}'" if self.description is not None else ""
        )
        raise ValidationError(f"❌ '{data.name}':{description_str} check failed")


class TypeValidator(SeriesValidator):
    """Validate a Series based on its type."""

    def __init__(self, dtypes: tuple[Union[DataTypeClass, pl.DataType], ...]):
        self.dtypes = dtypes

    def __call__(self, data: pl.Series):
        actual = data.dtype
        for dtype in self.dtypes:
            if isinstance(dtype, DataTypeClass):
                matches = isinstance(actual, dtype)
            elif isinstance(dtype, pl.DataType):
                matches = dtype == actual
            else:
                raise TypeError(f"Unsupported dtype: {dtype}")

            if matches:
                return

        # no match
        expected_str = (
            str(self.dtypes[0]) if len(self.dtypes) == 1 else f"one of {self.dtypes}"
        )
        raise ValidationError(
            f"❌ {data.name}: type check failed. Expected {expected_str}, got {data.dtype}"
        )


NOT_NULL = SeriesExpressionValidator(THIS.is_not_null(), "not null")


def IsNotNull():
    return NOT_NULL


def IsBetween(lower_bound, upper_bound, closed: ClosedInterval = "both"):
    """Validate a Series is between two values."""
    return SeriesExpressionValidator(
        THIS.is_between(lower_bound, upper_bound, closed),
        f"range ({lower_bound}, {upper_bound})",
    )


def IsIn(values):
    return SeriesExpressionValidator(THIS.is_in(values), f"in set {values}")


def ContainsPattern(pattern: str, literal: bool = False):
    """Validate a Series matches a regex pattern."""
    return SeriesExpressionValidator(
        THIS.str.contains(pattern, literal=literal), f"pattern {pattern}"
    )
