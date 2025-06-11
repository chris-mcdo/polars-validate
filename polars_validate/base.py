"""Base validation interfaces."""

import polars as pl


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(self, message: str):
        self.message = message


class Validator:
    """Validate a Polars DataFrame."""

    def __call__(self, data: pl.DataFrame) -> None:
        """Validate a DataFrame.

        Args:
            data (pl.DataFrame): The DataFrame to validate.

        Raises:
            ValidationError: If the DataFrame fails validation.
        """
        pass
