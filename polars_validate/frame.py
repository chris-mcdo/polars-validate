"""DataFrame validators."""

from typing import Callable, Optional

import polars as pl

from polars_validate.base import ValidationError, Validator
from polars_validate.constants import _IS_VALID, OFFSET
from polars_validate.series import SeriesValidator


class ValidatorGroup(Validator):
    """Run a sequence of DataFrame validators."""

    def __init__(self, validators: tuple[Validator, ...], eager: bool = False):
        self.validators = validators
        self.eager = eager

    def __call__(self, data: pl.DataFrame) -> None:
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
                f"Validation failed with {len(errors)} errors"
                f" ({num_success} passed):\n{errors_str}",
            )


class ColumnValidator(Validator):
    """Validate a column in a DataFrame."""

    def __init__(self, column: str, validator: SeriesValidator):
        self.column = column
        self.validator = validator

    def __call__(self, data: pl.DataFrame) -> None:
        self.validator(data.get_column(self.column))


class ExpressionValidator(Validator):
    """Validate a DataFrame based on an arbitrary expression."""

    def __init__(self, expression: pl.Expr, description: Optional[str] = None):
        self.description = description
        self.expression = expression

    def __call__(self, data: pl.DataFrame):
        invalid_items = (
            data.with_columns(self.expression.alias(_IS_VALID))
            .with_row_index(OFFSET)
            .filter(pl.col(_IS_VALID).eq(False))
            .get_column(OFFSET)
        )
        if not invalid_items.is_empty():
            raise ValidationError(f"{self.description} at offsets:\n{invalid_items}")


class CallableValidator(Validator):
    """Validate a DataFrame based on an arbitrary `Callable[[pl.DataFrame], bool]`."""

    def __init__(
        self, func: Callable[[pl.DataFrame], bool], description: Optional[str] = None
    ):
        self.func = func
        self.description = description

    def __call__(self, data: pl.DataFrame):
        result = self.func(data)
        if not isinstance(result, bool):
            raise TypeError(
                "Return value of CallableValidator function must be boolean,"
                f" got {type(result)}"
            )

        description_str = (
            f" '{self.description}'" if self.description is not None else ""
        )
        raise ValidationError(f"❌{description_str} check failed")


class UniqueTogether(Validator):
    """Validate that a set of columns are unique together."""

    def __init__(self, columns: tuple[str, ...]):
        self.columns = columns

    def __call__(self, data: pl.DataFrame) -> None:
        is_unique = data.select(self.columns).is_unique().alias(_IS_VALID)
        duplicates = (
            data.with_row_index(OFFSET)
            .with_columns(is_unique)
            .filter(pl.col(_IS_VALID).eq(False))
            .select(OFFSET, *self.columns)
        )
        if not duplicates.is_empty():
            raise ValidationError(
                f"uniqueness of columns {self.columns}:\n{duplicates}"
            )
