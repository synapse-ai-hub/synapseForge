"""Unified response contract for all tools, endpoints and the Agent.

Defines the unified JSON structure that every framework component must return
to ensure consistency across the entire API.
"""

from typing import Any, Optional, TypedDict


class UsageReport(TypedDict):
    """Token usage and execution time report.

    Attributes:
        prompt_tokens: Number of input tokens (prompt).
        completion_tokens: Number of output tokens (completion).
        total_tokens: Sum of prompt_tokens + completion_tokens.
        total_time: Total execution time in seconds.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_time: float


class ContractResponse(TypedDict):
    """Unified response structure for the entire API.

    Attributes:
        status: Indicates whether the operation was successful. ``"success"`` or ``"error"``.
        message: Human-readable description of the result.
        data: Any data associated with the response. ``None`` on error.
        usage: Token usage and execution time report.
    """

    status: str  # "success" | "error"
    message: str
    data: Any
    usage: UsageReport


def validate_response(response: dict) -> ContractResponse:
    """Validate that a dictionary complies with the unified response contract.

    Checks for the presence and correct types of the required keys
    (``status``, ``message``, ``data``). If the ``usage`` key is present,
    its internal structure is also validated.

    Args:
        response: Dictionary to validate.

    Returns:
        The same dictionary if validation succeeds.

    Raises:
        ValueError: If required keys are missing or have incorrect types.
        TypeError: If the ``response`` argument is not a dictionary.
    """
    
    if not isinstance(response, dict):
        raise TypeError(f"Expected dict, got {type(response).__name__}")

    required_keys = ["status", "message", "data"]
    for key in required_keys:
        if key not in response:
            raise ValueError(f"Missing required key: '{key}'")

    if response["status"] not in ("success", "error"):
        raise ValueError(
            f"Invalid status '{response['status']}'. Must be 'success' or 'error'"
        )

    if not isinstance(response["message"], str):
        raise ValueError(
            f"Field 'message' must be a string, got {type(response['message']).__name__}"
        )

    if "usage" in response and response["usage"] is not None:
        usage = response["usage"]
        if not isinstance(usage, dict):
            raise ValueError(
                f"Field 'usage' must be a dict, got {type(usage).__name__}"
            )

        usage_required_keys = [
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "total_time",
        ]
        missing_usage = [k for k in usage_required_keys if k not in usage]
        if missing_usage:
            raise ValueError(
                f"Missing required keys in 'usage': {', '.join(missing_usage)}"
            )

        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if key in usage:
                value = usage[key]
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(
                        f"Field 'usage.{key}' must be an int, "
                        f"got {type(value).__name__}"
                    )

        if "total_time" in usage:
            value = usage["total_time"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"Field 'usage.total_time' must be a number, "
                    f"got {type(value).__name__}"
                )

    return response


def make_success_response(
    message: str, data: Any = None, usage: Optional[UsageReport] = None
) -> ContractResponse:
    """Create a success response using the unified contract.

    Args:
        message: Human-readable description of the successful result.
        data: Data associated with the response (optional, defaults to ``None``).
        usage: Token usage and time report (optional).

    Returns:
        Dictionary with the ``ContractResponse`` structure in ``"success"`` status.
    """
    response: dict = {
        "status": "success",
        "message": message,
        "data": data,
        "usage": usage if usage is not None else zero_usage(),
    }
    return response


def make_error_response(message: str, usage: Optional[UsageReport] = None) -> ContractResponse:
    """Create an error response using the unified contract.

    Args:
        message: Human-readable description of the error that occurred.
        usage: Token usage and time report (optional).

    Returns:
        Dictionary with the ``ContractResponse`` structure in ``"error"`` status.
    """
    response: dict = {
        "status": "error",
        "message": message,
        "data": None,
        "usage": usage if usage is not None else zero_usage(),
    }
    return response


def zero_usage() -> UsageReport:
    """Return a usage report with all values set to zero.

    Returns:
        Dictionary with the ``UsageReport`` structure initialized to zero.
    """
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_time": 0.0,
    }
