"""
CampusGrid AI: Agent 2 — Input Series Validation
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

Every simulation input is a per-interval series, and the physics loops walk them in step.
Python's zip() silently stops at the shortest one, so a 48-interval weather forecast paired
with a 24-interval occupancy list used to produce a 24-interval "day" with no warning, and a
battery plan one interval short simply skipped its last step. Mismatched lengths are now a
hard error, raised before any physics runs.
"""

from typing import Optional, Sequence

from src.domain.exceptions.base import DomainException


class SeriesLengthMismatchError(DomainException, ValueError):
    """Per-interval input series of different lengths.

    Also a ValueError, so the MCP server and SimulationTool, which treat ValueError as
    "invalid arguments", reject it with the same error shape as any other bad input.
    """

    def __init__(self, lengths: dict):
        described = ", ".join(f"{name}={length}" for name, length in lengths.items())
        super().__init__(
            message=f"Per-interval series must all be the same length; got {described}.",
            error_code="SERIES_LENGTH_MISMATCH",
            details={"lengths": dict(lengths)},
        )


def require_equal_lengths(**series: Optional[Sequence]) -> int:
    """Returns the common length of every series given (None entries are skipped), or raises."""
    lengths = {name: len(values) for name, values in series.items() if values is not None}
    if len(set(lengths.values())) > 1:
        raise SeriesLengthMismatchError(lengths)
    return next(iter(lengths.values()), 0)
