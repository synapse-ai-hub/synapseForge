"""Contrato único de respuesta para todas las tools, endpoints y el Agent.

Define la estructura JSON unificada que todo componente del framework debe retornar
para garantizar consistencia en toda la API.
"""

from typing import Any, NotRequired, Optional, TypedDict


class UsageReport(TypedDict):
    """Reporte de uso de tokens y tiempo de ejecución.

    Attributes:
        prompt_tokens: Cantidad de tokens de entrada (prompt).
        completion_tokens: Cantidad de tokens de salida (completion).
        total_tokens: Suma de prompt_tokens + completion_tokens.
        total_time: Tiempo total de ejecución en segundos.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_time: float


class ContractResponse(TypedDict):
    """Estructura de respuesta única para toda la API.

    Attributes:
        status: Indica si la operación fue exitosa. ``"success"`` o ``"error"``.
        message: Descripción legible del resultado.
        data: Cualquier tipo de dato asociado a la respuesta. ``None`` en caso de error.
        tool_calls: Lista de tool calls solicitadas por el LLM (opcional).
        usage: Reporte de uso de tokens y tiempo de ejecución.
    """

    status: str  # "success" | "error"
    message: str
    data: Any
    tool_calls: NotRequired[Any]
    usage: UsageReport


def validate_response(response: dict) -> dict:
    """Valida que un diccionario cumpla con el contrato único de respuesta.

    Verifica la presencia y tipos correctos de las claves obligatorias
    (``status``, ``message``, ``data``). Si la clave ``usage`` está presente,
    también valida su estructura interna.

    Args:
        response: Diccionario a validar.

    Returns:
        El mismo diccionario si la validación es exitosa.

    Raises:
        ValueError: Si faltan claves obligatorias o sus tipos son incorrectos.
        TypeError: Si el argumento ``response`` no es un diccionario.
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
    message: str, data: Any = None, usage: Optional[UsageReport] = None,
    tool_calls: Any = None,
) -> dict:
    """Crea una respuesta de éxito con el contrato único.

    Args:
        message: Descripción legible del resultado exitoso.
        data: Datos asociados a la respuesta (opcional, ``None`` por defecto).
        usage: Reporte de uso de tokens y tiempo (opcional).
        tool_calls: Lista de tool calls solicitadas por el LLM (opcional).

    Returns:
        Diccionario con la estructura ``ContractResponse`` en estado ``"success"``.
    """
    response: dict = {
        "status": "success",
        "message": message,
        "data": data,
        "tool_calls": tool_calls,
        "usage": usage if usage is not None else zero_usage(),
    }
    return response


def make_error_response(message: str, usage: Optional[UsageReport] = None) -> dict:
    """Crea una respuesta de error con el contrato único.

    Args:
        message: Descripción legible del error ocurrido.
        usage: Reporte de uso de tokens y tiempo (opcional).

    Returns:
        Diccionario con la estructura ``ContractResponse`` en estado ``"error"``.
    """
    response: dict = {
        "status": "error",
        "message": message,
        "data": None,
        "tool_calls": None,
        "usage": usage if usage is not None else zero_usage(),
    }
    return response


def zero_usage() -> dict:
    """Retorna un reporte de uso (usage report) con todos los valores en cero.

    Returns:
        Diccionario con la estructura ``UsageReport`` inicializada en cero.
    """
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_time": 0.0,
    }


if __name__ == '__main__':
    print('Contract module — define make_success_response, make_error_response, zero_usage.')
    u = zero_usage()
    print(f'  zero_usage(): {u}')
    s = make_success_response(message='OK', data={'test': 1}, usage=u)
    print(f'  make_success_response: status={s["status"]}')
    e = make_error_response(message='Error', usage=u)
    print(f'  make_error_response: status={e["status"]}')
