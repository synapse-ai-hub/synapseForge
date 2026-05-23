"""
Agent class - Core LLM interaction and utility methods for synapseForge.

Provides the foundational Agent entity that encapsulates model configuration,
tool management, memory, streaming, retry logic, and prompt loading.
All public methods return the unified contract format ``{status, message, data, usage}``.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Generator, Optional

from dotenv import load_dotenv
import groq

from backend.utils.contract import (
    ContractResponse,
    UsageReport,
    make_error_response,
    make_success_response,
    validate_response,
    zero_usage,
)

# ---------------------------------------------------------------------------
# Project path setup
# ---------------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Marcadores de comentarios usados en este proyecto:
# TODO   : trabajo pendiente, todavía no implementado.
# FIXME  : hay un bug conocido; este código falla o es incorrecto.
# REVIEW : parte del código que debe ser revisada o validada por otra persona.
# NOTE   : aclaración importante sobre decisiones o comportamiento no obvio.
# HACK   : solución provisoria / poco elegante / hardcodeada, usada para salir del paso.
# DEBUG  : código o mensajes usados solo para depuración temporal.
# OK     : bloque probado y estable en las condiciones actuales.
# PROD   : código / config específica de producción; tocar con extremo cuidado.
# ---------------------------------------------------------------------------

load_dotenv()


class Agent:
    """Core class for interacting with LLMs with integrated logging, file management
    and the unified contract response format.

    Centralises interaction with Groq-based models (and, by extension, any
    OpenAI-compatible API) and provides helpers for cleaning outputs, file I/O,
    retry with exponential backoff, streaming, and prompt loading.

    Attributes:
        db: Optional database instance for prompt/vector access.
        model_qwen: Model identifier for the Qwen model (from ``MODEL_NAME_2`` env var).
        model_openai: Model identifier for the primary LLM (from ``MODEL_NAME_3`` env var).
        model_openai_small: Model identifier for smaller / cheaper LLM (from ``MODEL_NAME_4`` env var).
        client: Instantiated Groq client.
        tools: Tools instance for accessing system tools.
        usage: Last request usage metrics as a tuple
            ``(prompt_tokens, completion_tokens, total_tokens, prompt_time, completion_time, total_time)``.

    Note:
        Requires a ``.env`` file with ``GROQ_API_KEY``, ``MODEL_NAME_2``,
        ``MODEL_NAME_3`` and ``MODEL_NAME_4`` defined.
    """

    def __init__(self, db: Any = None) -> None:
        """Initialise the Agent.

        Loads environment variables for API keys and model names, instantiates
        the Groq client, and prepares the tools and prompt-caching subsystems.

        Args:
            db: Optional database instance for prompt / vector access. Passed
                from callers to avoid circular imports and to reuse a single DB instance.
        """
        super().__init__()

        self.db = db

        # -- Environment configuration -------------------------------------------
        self.__api_key = os.getenv("GROQ_API_KEY")
        self.model_qwen = os.getenv("MODEL_NAME_2")
        self.model_openai = os.getenv("MODEL_NAME_3")
        self.model_openai_small = os.getenv("MODEL_NAME_4")

        # -- Groq client ---------------------------------------------------------
        self.client = groq.Groq(api_key=self.__api_key)
        self.usage: Optional[tuple] = None

        # -- Prompt cache (avoids repeated file reads) --------------------------
        self._prompt_cache: Dict[str, str] = {}
        # agent.py lives in backend/utils/ -> go up 2 levels to project root
        self._prompts_dir = os.path.join(PROJECT_ROOT, "intelligence", "prompts")

        # -- Tools ----------------------------------------------------------------
        # Lazy-import to avoid circular dependency at module level.
        from backend.utils.tools import Tools  # type: ignore[import-untyped]

        self.tools = Tools(agent_instance=self, db_instance=self.db)

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def llm_process(
        self,
        model: str,
        prompt: str,
        system_content: str = "",
        temperature: float = 0.5,
        top_p: float = 0.5,
        max_tokens: int = 3000,
        cleaned_output: bool = True,
        **kwargs: Any,
    ) -> ContractResponse:
        """Send a chat completion request and return the response and usage metrics.

        Args:
            model: Model name to use for completion.
            prompt: User prompt or query.
            system_content: System instruction to guide the assistant. Defaults to ``""``.
            temperature: Sampling temperature. Defaults to ``0.5``.
            top_p: Nucleus sampling parameter. Defaults to ``0.5``.
            max_tokens: Maximum number of tokens to generate. Defaults to ``3000``.
            cleaned_output: If ``True``, the returned text is passed through
                :meth:`clean`. Defaults to ``True``.
            **kwargs: Additional keyword arguments forwarded to the Groq client.

        Returns:
            dict: Contract response with ``status``, ``message``, ``data``, and ``usage``.

        Note:
            If the returned output is empty a warning is printed. Exceptions are
            caught and returned as an error contract.
        """
        try:
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                **kwargs,
            )

            output = response.choices[0].message.content
            if output is None:
                output = ""
            if cleaned_output:
                output = self.clean(output)

            completion_tokens = response.usage.completion_tokens
            prompt_tokens = response.usage.prompt_tokens
            total_tokens = response.usage.total_tokens
            total_time = round(response.usage.total_time, 2)

            if not output:
                print(
                    f"La respuesta está vacía. Modelo: {model}, "
                    f"completion_tokens: {completion_tokens}, "
                    f"max_tokens: {max_tokens}. "
                    f"Posible truncamiento o razonamiento oculto. Revisar límite de tokens.",
                    flush=True,
                )

            return validate_response(
                make_success_response(
                    message="Proceso ok.",
                    data=output,
                    usage={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                        "total_time": total_time,
                    },
                )
            )

        except Exception as e:
            print(f"Error al procesar con LLM.\n{str(e)}")
            return validate_response(
                make_error_response(
                    message=str(e),
                    usage={
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "total_time": 0,
                    },
                )
            )

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def llm_stream(
        self,
        model: str,
        prompt: str,
        system_content: str = "",
        temperature: float = 0.5,
        top_p: float = 0.5,
        max_tokens: int = 3000,
        cleaned_output: bool = True,
        **kwargs: Any,
    ) -> Generator:
        """Stream a chat completion response from the Groq API.

        This generator yields content chunks as they arrive. Usage statistics
        are saved to ``self.usage`` after the stream completes.

        Args:
            model: Model name to use for completion.
            prompt: User prompt or query.
            system_content: System instruction. Defaults to ``""``.
            temperature: Sampling temperature. Defaults to ``0.5``.
            top_p: Nucleus sampling parameter. Defaults to ``0.5``.
            max_tokens: Maximum tokens to generate. Defaults to ``3000``.
            cleaned_output: If ``True``, each yielded chunk is cleaned. Defaults to ``True``.
            **kwargs: Additional keyword arguments forwarded to the Groq client.

        Yields:
            str: Cleaned (or raw) content chunk from the model.
        """
        try:
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            usage = None
            for chunk in response:
                if chunk.usage is not None:
                    usage = chunk.usage
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    if cleaned_output:
                        content = self.clean(content)
                    yield content

            if usage is not None:
                self.usage = (
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                    usage.prompt_time,
                    usage.completion_time,
                    usage.total_time,
                )
            else:
                self.usage = (0, 0, 0, 0.0, 0.0, 0.0)

        except Exception as e:
            print(f"Error al procesar con LLM.\n{str(e)}")
            yield f"Error: {str(e)}"

    async def llm_streaming(
        self,
        model: str,
        prompt: str,
        system_content: str = "",
        temperature: float = 0,
        top_p: float = 0.5,
        max_tokens: int = 3000,
        cleaned_output: bool = True,
        stream_cancel_event: Any = None,
        **kwargs: Any,
    ):
        """Async generator that streams LLM response chunks with cancellation support.

        Wraps :meth:`llm_stream` in an async context.  After each chunk, yields
        control to the event loop and checks the cancellation event.

        Args:
            model: Model name.
            prompt: User prompt.
            system_content: System instruction. Defaults to ``""``.
            temperature: Sampling temperature. Defaults to ``0``.
            top_p: Nucleus sampling parameter. Defaults to ``0.5``.
            max_tokens: Maximum tokens. Defaults to ``3000``.
            cleaned_output: Clean each chunk. Defaults to ``True``.
            stream_cancel_event: Optional threading ``Event`` to check for cancellation.
            **kwargs: Additional keyword arguments.

        Yields:
            dict: ``{"type": "chunk", "content": str}`` for each content chunk, or
            ``{"type": "aborted"}`` if cancelled mid-stream.
        """
        for chunk in self.llm_stream(
            model,
            prompt,
            system_content=system_content,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            cleaned_output=cleaned_output,
            **kwargs,
        ):
            if stream_cancel_event and stream_cancel_event.is_set():
                yield {"type": "aborted"}
                return
            yield {"type": "chunk", "content": chunk}
            await asyncio.sleep(0.01)

    # ------------------------------------------------------------------
    # Web search (compound model)
    # ------------------------------------------------------------------

    def web_search(
        self,
        query: str,
        temperature: float = 0.5,
        top_p: float = 0.5,
        max_tokens: int = 8192,
        cleaned_output: bool = True,
        **kwargs: Any,
    ) -> ContractResponse:
        """Perform a web-search style request using the Groq compound model.

        Args:
            query: User query for the web search.
            temperature: Sampling temperature. Defaults to ``0.5``.
            top_p: Nucleus sampling parameter. Defaults to ``0.5``.
            max_tokens: Maximum tokens. Defaults to ``8192``.
            cleaned_output: If ``True`` the result is cleaned. Defaults to ``True``.
            **kwargs: Additional keyword arguments.

        Returns:
            dict: Contract response with the search results in ``data``.
        """
        try:
            messages = [{"role": "user", "content": query}]
            response = self.client.chat.completions.create(
                model="groq/compound",
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=False,
                **kwargs,
            )

            output = response.choices[0].message.content
            if cleaned_output:
                output = self.clean(output)

            return validate_response(
                make_success_response(message="Búsqueda web completada.", data=output)
            )

        except Exception as e:
            print(f"Error al procesar búsqueda web con LLM.\n{str(e)}")
            return validate_response(make_error_response(message=str(e)))

    # ------------------------------------------------------------------
    # Text cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def clean(text: str) -> str:
        """Remove special Unicode characters and formatting artifacts.

        The cleaning is deliberately conservative: zero-width and non-standard
        space characters, several dash variants and invisible markers are replaced.

        Args:
            text: Input text to clean.

        Returns:
            str: Cleaned text.
        """
        text = text.replace("\ufeff", "")
        text = text.replace("\u202f", " ")  # narrow no-break space -> normal space
        text = text.replace("\u2011", "-")  # non-breaking hyphen -> normal hyphen
        text = text.replace("\u2013", "-")  # en dash -> hyphen
        text = text.replace("\u2014", "-")  # em dash -> hyphen
        text = text.replace(chr(8209), "-")
        text = text.replace("\u200b", "")  # zero-width space
        return text

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    async def load_text(self, load_path: str, encoding: str | None = "utf-8") -> ContractResponse:
        """Load the contents of a text file.

        Args:
            load_path: Path to the file to load.
            encoding: File encoding. Defaults to ``"utf-8"``.

        Returns:
            dict: Contract response with the file content in ``data``.
        """
        try:
            with open(load_path, "r", encoding=encoding) as f:
                text = f.read()
            return validate_response(
                make_success_response(message="Archivo cargado correctamente.", data=text)
            )
        except Exception as e:
            print(f"Error en carga de archivo. Verifique ruta especificada o compatibilidad.\n{e}")
            return validate_response(
                make_error_response(
                    message=f"Error en carga de archivo. Verifique ruta especificada o compatibilidad.\n{e}"
                )
            )

    async def save(
        self,
        save_path: str,
        element: str | dict,
        encoding: str | None = "utf-8",
        is_json: bool = False,
    ) -> None:
        """Save a string or dictionary to the filesystem.

        Args:
            save_path: Destination file path.
            element: Content to save. If ``is_json`` is ``True``, must be JSON-serializable.
            encoding: File encoding. Defaults to ``"utf-8"``.
            is_json: When ``True``, dump the element as pretty-printed JSON.
        """
        try:
            if not is_json:
                with open(save_path, "w", encoding=encoding) as f:
                    f.write(element)
            else:
                with open(save_path, "w", encoding=encoding) as f:
                    json.dump(element, f, ensure_ascii=False, indent=4)

            print(f"Archivo guardado en: {save_path}")
        except Exception as e:
            print(f"Error en guardado. Verifique ruta especificada o elemento.\n{e}")

    # ------------------------------------------------------------------
    # Timestamp helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_timestamp(weekday_bool: bool = False) -> str:
        """Generate a timestamp string.

        Args:
            weekday_bool: If ``True``, returns the Spanish name of the current weekday.

        Returns:
            str: Weekday name or compact timestamp ``ddmmyyHHMMSSmmm``.
        """
        dias = {
            0: "Lunes",
            1: "Martes",
            2: "Miércoles",
            3: "Jueves",
            4: "Viernes",
            5: "Sábado",
            6: "Domingo",
        }
        if weekday_bool:
            return dias[datetime.now().weekday()]
        now = datetime.now()
        return now.strftime("%d%m%y%H%M%S") + f"{now.microsecond // 1000:03d}"

    @staticmethod
    def date_format(raw_date: str) -> str:
        """Convert a raw timestamp into a human-readable date string.

        The input is expected in the format produced by :meth:`get_timestamp`
        (``ddmmyyHHMMSSmmm``).

        Args:
            raw_date: Raw timestamp string.

        Returns:
            str: Formatted date ``dd/mm/yy-HH:MM:SS``.
        """
        day = raw_date[:2]
        month = raw_date[2:4]
        year = raw_date[4:6]
        hour = raw_date[6:8]
        minute = raw_date[8:10]
        second = raw_date[10:12]
        return f"{day}/{month}/{year}-{hour}:{minute}:{second}"

    # ------------------------------------------------------------------
    # Retry with exponential backoff
    # ------------------------------------------------------------------

    async def retry(self, name: str, attempts: int = 3, **kwargs: Any) -> ContractResponse:
        """Execute an LLM call with retry logic and exponential backoff.

        The method performs up to **3 rounds** of retries.  Within each round,
        up to ``attempts`` LLM calls are made.  If the response data is empty
        the call is retried.  The response is then parsed as JSON; if parsing
        fails, the error is accumulated and a new round is attempted with the
        error history injected into the prompt.

        Args:
            name: Logical name for the operation (used in log messages).
            attempts: Maximum LLM attempts per round. Defaults to ``3``.
            **kwargs: Arguments forwarded to :meth:`llm_process`.

        Returns:
            dict: Contract response.
        """
        errors: list[str] = []
        response = None
        response_json = None

        for j in range(3):
            round_kwargs = dict(kwargs)
            if j > 0 and errors:
                round_kwargs["prompt"] = (
                    kwargs.get("prompt", "")
                    + f"\n\n---\n\nTen en cuenta los siguientes errores previos:\n{errors}"
                )

            # --- Step A: get LLM response (retry on empty / exception) ----------
            for i in range(attempts + 1):
                if i == attempts:
                    return validate_response(
                        make_error_response(message="Error al generar respuesta con LLM")
                    )

                try:
                    response = self.llm_process(**round_kwargs)
                    if not response.get("data"):
                        await asyncio.sleep(2 ** (i + 1))
                        continue
                    break
                except Exception as e:
                    if i == attempts and j == 2:
                        return validate_response(make_error_response(message=str(e)))

                    print(f"Error de request {name}, intento {i + 1}:\n{str(e)}")
                    await asyncio.sleep(2 ** (i + 1))
                    continue

            # --- Step B: parse JSON from the response data --------------------
            for i in range(attempts + 1):
                try:
                    response_json = json.loads(response["data"])
                    break
                except Exception as e:
                    if i == attempts and j == 2:
                        return validate_response(make_error_response(message=str(e)))

                    print(f"Error de json {name}, intento {i + 1}:\n{str(e)}")
                    errors.append(str(e))
                    await asyncio.sleep(1)
                    continue

            # If parsing succeeded, exit the outer rounds loop
            if response_json is not None:
                break

        # -- Build final response ------------------------------------------------
        if "CoD" in name:
            response["status"] = "success"
            response["message"] = "CoD finalizado"
            response["data"] = response_json
        else:
            response["status"] = response_json.get("status", "error")
            response["message"] = response_json.get("message", "Unknown error")
            response["data"] = response_json.get("data", None)

        return response

    # ------------------------------------------------------------------
    # Usage metrics aggregator
    # ------------------------------------------------------------------

    async def usage_metrics(self, usage_dict: UsageReport | None, **kwargs: Any) -> UsageReport:
        """Update a cumulative usage dictionary with additional metric values.

        Args:
            usage_dict: Current cumulative metrics dict (may be ``None``).
            **kwargs: Metric values to add (``prompt_tokens``, ``completion_tokens``,
                ``total_tokens``, ``total_time``).

        Returns:
            dict: Updated usage dictionary.
        """
        try:
            if usage_dict is None:
                usage_dict = {}
            usage_dict["prompt_tokens"] = (
                usage_dict.get("prompt_tokens", 0) + kwargs.get("prompt_tokens", 0)
            )
            usage_dict["completion_tokens"] = (
                usage_dict.get("completion_tokens", 0) + kwargs.get("completion_tokens", 0)
            )
            usage_dict["total_tokens"] = (
                usage_dict.get("total_tokens", 0) + kwargs.get("total_tokens", 0)
            )
            usage_dict["total_time"] = round(
                usage_dict.get("total_time", 0) + kwargs.get("total_time", 0), 2
            )
            return usage_dict
        except (KeyError, TypeError):
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "total_time": 0,
            }

    # ------------------------------------------------------------------
    # Pipeline sub-agents
    # ------------------------------------------------------------------

    async def router(self, prompt: str = "", system_content: str = "") -> ContractResponse:
        """Router stage: decide if the query requires planning or direct response.

        Uses the small/cheap model (``model_openai_small``).

        Args:
            prompt: The router prompt.
            system_content: System instructions.

        Returns:
            ContractResponse: Response with routing decision.
        """
        return await self.retry(
            "Router",
            model=self.model_openai_small,
            prompt=prompt,
            system_content=system_content or "",
            temperature=0,
            top_p=0.3,
            max_tokens=500,
            cleaned_output=True,
            reasoning_effort="low",
        )

    async def planner(self, prompt: str = "", system_content: str = "") -> ContractResponse:
        """Planner stage: generate an execution plan for complex tasks.

        Uses the primary model (``model_openai``).

        Args:
            prompt: The planner prompt.
            system_content: System instructions.

        Returns:
            ContractResponse: Response with the execution plan.
        """
        return await self.retry(
            "Planner",
            model=self.model_openai,
            prompt=prompt,
            system_content=system_content,
            temperature=0,
            top_p=0.3,
            max_tokens=3000,
            cleaned_output=True,
            reasoning_effort="high",
        )

    async def decision_maker(self, prompt: str = "", system_content: str = "") -> ContractResponse:
        """Decision Maker stage: translate a step description into executable parameters.

        Uses the small/cheap model (``model_openai_small``).

        Args:
            prompt: The decision maker prompt.
            system_content: System instructions.

        Returns:
            ContractResponse: Response with tool name and parameters.
        """
        return await self.retry(
            "Decision Maker",
            model=self.model_openai_small,
            prompt=prompt,
            temperature=0,
            top_p=0.3,
            max_tokens=3000,
            cleaned_output=True,
            reasoning_effort="medium",
        )

    async def validator(self, prompt: str = "", system_content: str = "") -> ContractResponse:
        """Validator stage: evaluate whether a tool's output meets the plan's requirements.

        Uses the primary model (``model_openai``).

        Args:
            prompt: The validator prompt.
            system_content: System instructions.

        Returns:
            ContractResponse: Response with validation result.
        """
        return await self.retry(
            "Validator",
            model=self.model_openai,
            prompt=prompt,
            system_content=system_content,
            temperature=0.4,
            top_p=0.7,
            max_tokens=3000,
            cleaned_output=True,
            reasoning_effort="high",
        )

    async def corrector(self, prompt: str = "", system_content: str = "") -> ContractResponse:
        """Corrector stage: apply corrections and regenerate output.

        Uses the primary model (``model_openai``).

        Args:
            prompt: The corrector prompt.
            system_content: System instructions.

        Returns:
            ContractResponse: Response with corrected output.
        """
        return await self.retry(
            "Corrector",
            model=self.model_openai,
            prompt=prompt,
            system_content=system_content,
            temperature=0.5,
            top_p=0.7,
            max_tokens=3000,
            cleaned_output=True,
            reasoning_effort="high",
        )

    # ------------------------------------------------------------------
    # Prompt loading
    # ------------------------------------------------------------------

    def prompt(self, name: str) -> str:
        """Retrieve a prompt by name.

        The lookup order is:
        1. In-memory cache (``self._prompt_cache``)
        2. Markdown file in ``intelligence/prompts/{name}.md``
        3. Vector store fallback (legacy, requires ``self.db``)

        Args:
            name: Prompt name (without extension).

        Returns:
            str: Prompt content, or ``""`` if not found.
        """
        # 1. Cache check
        if name in self._prompt_cache:
            return self._prompt_cache[name]

        # 2. File load
        content = self._load_prompt_from_file(name)
        if content is not None:
            self._prompt_cache[name] = content
            return content

        # 3. Legacy vector-store fallback
        if self.db is not None:
            try:
                result = self.db.retrieve_vector("prompt", name)
                if result:
                    self._prompt_cache[name] = result
                    return result
            except Exception as e:
                print(f"Warning: DB prompt retrieval failed for '{name}': {e}")

        return ""

    @staticmethod
    def _validate_prompt_name(name: str) -> bool:
        """Validate that the prompt name does not contain path-traversal patterns.

        Args:
            name: Prompt name to validate.

        Returns:
            ``True`` if the name is safe, ``False`` otherwise.
        """
        if not name or not name.strip():
            return False
        if ".." in name or "/" in name or "\\" in name or "\x00" in name:
            return False
        return True

    def _load_prompt_from_file(self, name: str) -> str | None:
        """Load a prompt from a file in ``self._prompts_dir``.

        Searches for ``{name}.md`` → ``{name}.txt`` → ``{name}`` (no extension).

        Args:
            name: Prompt name.

        Returns:
            str: File content, or ``None`` if not found.
        """
        if not self._validate_prompt_name(name):
            return None

        extensions = [".md", ".txt", ""]
        for ext in extensions:
            filepath = os.path.join(self._prompts_dir, f"{name}{ext}")
            if os.path.isfile(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        return f.read()
                except (OSError, UnicodeDecodeError) as e:
                    print(f"Error reading prompt file {filepath}: {e}")
                    return None
        return None


if __name__ == "__main__":
    print("Agent module for LLM interaction and various utilities.")
