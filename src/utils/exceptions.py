"""Custom exceptions for DuckLens."""


class DuckLensError(Exception):
    """Base exception for all DuckLens errors."""

    pass


class DataCollectionError(DuckLensError):
    """Raised when data collection fails."""

    pass


class ValidationError(DuckLensError):
    """Raised when data validation fails."""

    pass


class ModelInferenceError(DuckLensError):
    """Raised when model prediction fails."""

    pass


class DatabaseError(DuckLensError):
    """Raised when database operation fails."""

    pass


class ConfigurationError(DuckLensError):
    """Raised when configuration is invalid."""

    pass
