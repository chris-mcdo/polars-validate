from typing import Annotated, Any, ClassVar, Literal, Union, get_args, get_origin

import polars as pl
from polars.datatypes.classes import DataTypeClass

from polars_validate.base import Validator
from polars_validate.frame import ColumnValidator, ExpressionValidator, ValidatorGroup
from polars_validate.series import (
    IsIn,
    SeriesExpressionValidator,
    SeriesValidator,
    SeriesValidatorGroup,
    TypeValidator,
)

SeriesValidatorSpec = Union[SeriesValidator, pl.Expr]
ValidatorSpec = Union[Validator, pl.Expr]

FrameValidators = ClassVar[tuple[ValidatorSpec, ...]]


def validate(schema, data: pl.DataFrame, eager: bool = False) -> None:
    """Validate a DataFrame against a schema.

    Args:
        schema: The schema to validate against.
        data (pl.DataFrame): The DataFrame to validate.

    Raises:
        ValidationError: If the DataFrame does not match the schema.
    """
    if not isinstance(data, pl.DataFrame):
        raise TypeError(f"Data must be a polars DataFrame, got {type(data)} instead.")
    validators = schema_to_validators(schema)
    validator = ValidatorGroup(validators, eager=eager)
    validator(data)


def validate_series(schema, data: pl.Series, eager: bool = False):
    if not isinstance(data, pl.Series):
        raise TypeError(f"Data must be a polars Series, got {type(data)} instead.")
    validators = schema_to_series_validators(schema)
    validator = SeriesValidatorGroup(validators, eager=eager)
    validator(data)


def spec_to_series_validator(spec: SeriesValidatorSpec) -> SeriesValidator:
    if isinstance(spec, SeriesValidator):
        return spec
    elif isinstance(spec, pl.Expr):
        return SeriesExpressionValidator(spec)
    else:
        raise TypeError(f"Unsupported spec: {spec}")


def spec_to_validator(spec: ValidatorSpec):
    if isinstance(spec, Validator):
        return spec
    elif isinstance(spec, pl.Expr):
        return ExpressionValidator(spec)
    else:
        raise TypeError(f"Unsupported spec: {spec}")


def schema_to_series_validators(annotation) -> tuple[SeriesValidator, ...]:
    """Convert a schema (type annotation) to a set of Series validators."""
    # Here are some examples of possible annotations:
    # * v(Optional[X]) -> (v(X), Nullable) -- not planned
    # * v(Union[X, Y]) -> UnionValidator(v(X), v(Y)) -- not planned
    # * Literal[X] -> IsIn(X)

    if isinstance(annotation, (pl.DataType, DataTypeClass)):
        return (TypeValidator((annotation,)),)
    elif get_origin(annotation) is Literal:
        return (IsIn(get_args(annotation)),)
    elif get_origin(annotation) is Annotated:
        args = get_args(annotation)
        dtype = args[0]
        metadata = args[1:]
        metadata_validators = (spec_to_series_validator(m) for m in metadata)
        return (TypeValidator((dtype,)), *metadata_validators)
    else:
        raise TypeError(f"Unsupported annotation: {annotation}")


def schema_to_validators(schema) -> tuple[Validator, ...]:
    """Convert a schema (class) to a set of DataFrame validators."""
    annotations: dict[str, Any] = schema.__annotations__

    # column validators
    column_to_validators = {
        k: schema_to_series_validators(v)
        for k, v in annotations.items()
        if v is not ClassVar and get_origin(v) is not ClassVar
    }
    all_column_validators = tuple(
        ColumnValidator(k, v)
        for k, validators in column_to_validators.items()
        for v in validators
    )

    dataframe_validator_fields = tuple(
        k for k, v in annotations.items() if v is ClassVar or get_origin(v) is ClassVar
    )
    dataframe_validators = tuple(
        spec_to_validator(v)
        for field in dataframe_validator_fields
        for v in getattr(schema, field, ())
    )

    return all_column_validators + dataframe_validators
