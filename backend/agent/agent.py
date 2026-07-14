import groq
import ollama
import sys
import os
import json
import time
import uuid
import functools
import logging
from datetime import datetime
from dotenv import load_dotenv
from typing import Any, Dict, Generator
import asyncio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# agent.py is at backend/utils/ -> need 3 dirname() calls to reach root.
# ---------------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.agent.utils.error_logger import log_error
from backend.agent.contract import (
    ContractResponse,
    UsageReport,
    make_error_response,
    make_success_response,
    validate_response,
    zero_usage,
)

from backend.agent.tools import Tools

# Marcadores de comentarios usados en este proyecto:
# TODO   : trabajo pendiente, todavía no implementado.
# FIXME  : hay un bug conocido; este código falla o es incorrecto.
# REVIEW : parte del código que debe ser revisada o validada por otra persona.
# NOTE   : aclaración importante sobre decisiones o comportamiento no obvio.
# HACK   : solución provisoria / poco elegante / hardcodeada, usada para salir del paso.
# DEBUG  : código o mensajes usados solo para depuración temporal.
# OK     : bloque probado y estable en las condiciones actuales.
# PROD   : código / config específica de producción; tocar con extremo cuidado.


load_dotenv()  

class Agent():
    '''
    Core class for interacting with LLMs (Groq API u Ollama local) with integrated logging and file management.

    This class centralizes interaction with LLM providers and provides helper
    utilities for cleaning outputs and simple file I/O.

    Selecciona el proveedor según la variable de entorno ``PROVIDER``:
      - ``API``  → usa Groq (OpenAI-compatible, necesita ``GROQ_API_KEY``).
      - ``LOCAL`` → usa Ollama (local, necesita ``ollama`` instalado y el servicio corriendo).

    ## Attributes:
        - __api_key (str): API key used to authenticate with the Groq client (loaded from environment).
        - model_qwen (str): Model identifier for the Qwen model (from MODEL_NAME_2 env var).
        - model_openai (str): Model identifier for the OpenAI-compatible model (from MODEL_NAME_3 env var).
        - provider (str): ``API`` o ``LOCAL`` según la variable de entorno ``PROVIDER``.
        - client (groq.Groq | None): Instantiated Groq client (solo si provider == ``API``).
        - ollama_client (ollama.Client | None): Instantiated Ollama client (solo si provider == ``LOCAL``).
        - usage (tuple | None): Last request usage metrics in the form
          (prompt_tokens, completion_tokens, total_tokens, prompt_time, completion_time, total_time).

    ## Notes:
        - Para provider ``API``: requiere ``.env`` con ``GROQ_API_KEY``, ``MODEL_NAME_2``, ``MODEL_NAME_3``.
        - Para provider ``LOCAL``: requiere ``ollama`` instalado (``pip install ollama``) y el servicio corriendo.
        - Methods that call the API catch exceptions and print errors rather than raising; callers should
          handle missing return values accordingly.

    ## Example:
        >>> from Utils.agent import Agent
        >>> agent = Agent()
        >>> resp, usage = agent.llm_process(agent.model_qwen, "What is the capital of France?")
        >>> print(resp)
        The capital of France is Paris.
    '''
 
    def __init__(self) -> None:
        '''
        Initialize the Agent.

        Always tries to instantiate both LLM clients (Groq and Ollama)
        regardless of availability.  If a client cannot be created (e.g.
        missing API key or Ollama not running), the corresponding attribute
        is set to ``None``.

        ``self.provider`` is initially ``None`` and is set by the
        ``POST /api/config/models/select`` endpoint when the user selects
        a model + provider from the frontend.

        ## Raises:
            - None: Exceptions during client creation are caught and the
              attribute is set to ``None``.
        '''
        super().__init__()

        self.__api_key = os.getenv('GROQ_API_KEY')
        self.provider: str | None = None
        self._resolved_model: str | None = None

        # Always try to create both clients.  The frontend dropdown will
        # only show providers whose client initialised successfully.
        try:
            self.groq_client = groq.Groq(api_key=self.__api_key)
        except Exception as e:
            log_error(str(e), source="agent.py:__init__(groq)")
            self.groq_client = None

        try:
            self.ollama_client = ollama.Client(host='http://localhost:11434')
        except Exception as e:
            log_error(str(e), source="agent.py:__init__(ollama)")
            self.ollama_client = None

        self.usage = None

        # Cache de prompts cargados desde archivos (evita lecturas repetitivas)
        self._prompt_cache: Dict[str, str] = {}
        # Ruta al directorio de prompts.
        # En desarrollo: intelligence/prompts/ relativo a la raiz del proyecto.
        # En compilado (PyInstaller): se toma de sys._MEIPASS (embebido con --add-data).
        if getattr(sys, 'frozen', False):
            _base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            _base = _project_root
        self._prompts_dir = os.path.join(_base, 'intelligence', 'prompts')

        self.tools = Tools()

    @property
    def default_model(self) -> str:
        """Return the resolved model name.

        The model must be selected via ``POST /api/config/models/select``
        (see :mod:`backend.routes.config`). If no model has been selected
        yet, returns an empty string.

        Returns:
            The selected model name string, or empty if not yet selected.
        """
        if self._resolved_model is not None:
            return self._resolved_model
        logger.warning("No model selected yet. Use POST /api/config/models/select to set one.")
        return ''

    def _normalize_tool_calls(self, tool_calls: list[Any] | None) -> list[dict[str, Any]] | None:
        """Normalize raw tool_calls to uniform ``{"id", "name", "args"}``.

        Args:
            tool_calls: Raw tool_calls from the API (Groq or Ollama format).

        Returns:
            Normalized list, or ``None`` if empty.
        """
        if not tool_calls:
            return None
        normalized = []
        for tc in tool_calls:
            entry: dict[str, Any] = {}
            try:
                entry["id"] = tc.id
            except AttributeError as e:
                log_error(str(e), source="agent.py:_normalize_tool_calls(id)")
                entry["id"] = ""
            # Groq always provides an id; Ollama may omit it. Generate one so
            # the assistant message and the tool result stay linked.
            if not entry["id"]:
                entry["id"] = f"call_{uuid.uuid4().hex}"
            try:
                entry["name"] = tc.function.name
            except AttributeError as e:
                log_error(str(e), source="agent.py:_normalize_tool_calls(name)")
                continue
            try:
                args_raw = tc.function.arguments
                if isinstance(args_raw, str):
                    entry["args"] = json.loads(args_raw) if args_raw else {}
                elif isinstance(args_raw, dict):
                    entry["args"] = args_raw
                else:
                    entry["args"] = {}
            except (AttributeError, json.JSONDecodeError) as e:
                log_error(str(e), source="agent.py:_normalize_tool_calls(args)")
                entry["args"] = {}
            normalized.append(entry)
        return normalized if normalized else None

    def _to_provider_tool_calls(
        self, tool_calls: list[dict[str, Any]], is_groq: bool
    ) -> list[dict[str, Any]]:
        """Convert normalized tool_calls to the SDK format each provider expects.

        Normalized tool_calls have the shape
        ``{"id", "name", "args"}``. Both Groq (OpenAI-compatible)
        and Ollama expect the wrapped shape
        ``{"id", "type": "function", "function": {"name", "arguments"}}``,
        but they differ in how ``arguments`` is encoded:

        - **Groq**: ``function.arguments`` must be a **JSON string**.
        - **Ollama**: ``function.arguments`` must be a **dict**.

        Args:
            tool_calls: Normalized list (``{"id", "name", "args"}``) or a
                list that is already in SDK format (has a ``function`` key).
            is_groq: ``True`` for Groq, ``False`` for Ollama.

        Returns:
            List of tool_calls in the provider's expected format.
        """
        out: list[dict[str, Any]] = []
        for tc in tool_calls:
           
            # the arguments encoding for the current provider.
            if "function" in tc:
                func = dict(tc["function"])
                args = func.get("arguments")
                if is_groq and isinstance(args, dict):
                    func["arguments"] = json.dumps(args, ensure_ascii=False)
                elif not is_groq and isinstance(args, str):
                    try:
                        func["arguments"] = json.loads(args)
                    except (json.JSONDecodeError, TypeError) as e:
                        log_error(str(e), source="agent.py:_to_provider_tool_calls(groq_args)")
                out.append(
                    {
                        "id": tc.get("id") or f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": func,
                    }
                )
                continue
            # Normalized format: {"id", "name", "args"}
            tc_id = tc.get("id") or f"call_{uuid.uuid4().hex}"
            args = tc.get("args", {})
            if is_groq:
                try:
                    func_args = json.dumps(args, ensure_ascii=False)
                except (TypeError, ValueError) as e:
                    log_error(str(e), source="agent.py:_to_provider_tool_calls(func_args)")
                    func_args = json.dumps({}, ensure_ascii=False)
            else:
                func_args = args
            out.append(
                {
                    "id": tc_id,
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": func_args,
                    }
                }
            )
        return out

    def llm_process(self, model: str, prompt: str | None = None,
                    system_content: str | None = None,
                    messages: list[dict[str, Any]] | None = None,
                    temperature: float | None = None,
                    top_p: float | None = None,
                    max_tokens: int | None = None,
                    cleaned_output: bool = True,
                    tools: list | None = None,
                    **kwargs) -> ContractResponse:
        """Send a chat completion and return content + tool_calls.

        Accepts either the classic ``prompt`` + ``system_content`` (backwards
        compatible) OR a full ``messages`` array.  When ``messages`` is
        provided, ``prompt`` and ``system_content`` are ignored.

        Args:
            model: Model name.
            prompt: User prompt (ignored if ``messages`` is set).
            system_content: System instruction (ignored if ``messages`` is set).
            messages: Full messages array (``role``, ``content``, ``tool_calls``, …).
            temperature: Sampling temperature (``None`` = provider default).
            top_p: Nucleus sampling (``None`` = provider default).
            max_tokens: Max output tokens (``None`` = provider default).
            cleaned_output: Apply ``self.clean()`` to text content.
            tools: Tool definitions for function calling.
            **kwargs: Forwarded to the provider client.

        Returns:
            ``ContractResponse`` with:
            - ``data`` — text content (cleaned if requested).
            - ``tool_calls`` — normalized list ``{"id", "name", "args"}`` or ``None``.
            - ``usage`` — token / time report.
        """
        try:
            # --- Build messages ---
            if messages is not None:
                is_groq = self.provider == 'API'
                msgs = []
                for m in messages:
                    m_copy = dict(m)
                    tcs = m_copy.get("tool_calls")
                    if tcs and isinstance(tcs, list):
                        m_copy["tool_calls"] = self._to_provider_tool_calls(tcs, is_groq)
                    msgs.append(m_copy)
            else:
                msgs = []
                if system_content:
                    msgs.append({'role': 'system', 'content': system_content})
                msgs.append({'role': 'user', 'content': prompt or ''})

            api_kwargs = {}
            if temperature is not None:
                api_kwargs['temperature'] = temperature
            if top_p is not None:
                api_kwargs['top_p'] = top_p
            if max_tokens is not None:
                api_kwargs['max_tokens'] = max_tokens

            if self.provider == 'API':
                # ── Groq (OpenAI-compatible) ──
                groq_kwargs = dict(api_kwargs)
                if tools:
                    groq_kwargs["tools"] = tools
                    groq_kwargs["tool_choice"] = "auto"
                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    **groq_kwargs,
                    **kwargs,
                )
                output = response.choices[0].message.content or ""
                raw_tc = response.choices[0].message.tool_calls
                if cleaned_output and output:
                    output = self.clean(output)
                completion_tokens = response.usage.completion_tokens
                prompt_tokens = response.usage.prompt_tokens
                total_tokens = response.usage.total_tokens
                total_time = round(response.usage.total_time, 2)

            elif self.provider == 'LOCAL':
                # ── Ollama (local) ──
                options = {}
                if temperature is not None:
                    options['temperature'] = temperature
                if top_p is not None:
                    options['top_p'] = top_p
                if max_tokens is not None:
                    options['num_predict'] = max_tokens
                for k in ('seed', 'num_ctx', 'top_k', 'min_p', 'repeat_penalty',
                          'frequency_penalty', 'presence_penalty', 'mirostat',
                          'mirostat_tau', 'mirostat_eta', 'typical_p', 'tfs_z',
                          'num_thread', 'num_gpu', 'stop'):
                    if k in kwargs:
                        options[k] = kwargs.pop(k)
                keep_alive_val = kwargs.pop('keep_alive', None)
                for k in list(kwargs):
                    print(f'[WARN] Ollama no soporta el parámetro "{k}". Será ignorado.', flush=True)
                    kwargs.pop(k)

                response = self.ollama_client.chat(
                    model=model,
                    messages=msgs,
                    tools=tools if tools else None,
                    options=options,
                    keep_alive=keep_alive_val,
                )
                output = response.message.content or ""
                raw_tc = response.message.tool_calls
                if cleaned_output and output:
                    output = self.clean(output)
                completion_tokens = response.eval_count or 0
                prompt_tokens = response.prompt_eval_count or 0
                total_tokens = (response.eval_count or 0) + (response.prompt_eval_count or 0)
                total_time = round((response.total_duration or 0) / 1_000_000_000, 2)
            else:
                return validate_response(make_error_response(message=f"PROVIDER inválido: '{self.provider}'"))

            tool_calls = self._normalize_tool_calls(raw_tc)

            return validate_response(make_success_response(
                message='Proceso ok.',
                data=output,
                tool_calls=tool_calls,
                usage={
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                    'total_time': total_time,
                },
            ))
        except Exception as e:
            print(f'Error al procesar con LLM.\n{str(e)}')
            log_error(str(e), source="agent.py:llm")
            return validate_response(make_error_response(
                message=str(e),
                usage={
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0,
                    'total_time': 0,
                },
            ))
     

    async def llm_streaming(self, model: str, prompt: str | None = None,
                             system_content: str = '',
                             messages: list[dict[str, Any]] | None = None,
                             temperature: float = 0,
                             top_p: float = 0.5, max_tokens: int = 3000,
                             cleaned_output: bool = True,
                             tools: list | None = None,
                             stream_cancel_event=None, **kwargs):
        """Async generator that streams LLM response chunks.

        Accepts either ``prompt`` + ``system_content`` (backwards compatible)
        OR a full ``messages`` array.  When ``messages`` is provided,
        ``prompt`` and ``system_content`` are ignored.

        During streaming, content chunks are yielded as:

        ``{'type': 'chunk', 'content': str}``

        If ``stream_cancel_event`` is set the generator yields
        ``{'type': 'aborted'}`` and stops.

        Args:
            model: Model name.
            prompt: User prompt (ignored if ``messages`` is set).
            system_content: System instruction (ignored if ``messages`` is set).
            messages: Full messages array.
            temperature: Sampling temperature.
            top_p: Nucleus sampling.
            max_tokens: Max output tokens.
            cleaned_output: Apply ``self.clean()`` to text chunks.
            tools: Tool definitions for function calling.
            stream_cancel_event: Optional event to cancel mid-stream.
            **kwargs: Forwarded to the provider client.

        Yields:
            Streaming event dicts.
        """
        if messages is not None:
            is_groq = self.provider == 'API'
            msgs = []
            for m in messages:
                m_copy = dict(m)
                tcs = m_copy.get("tool_calls")
                if tcs and isinstance(tcs, list):
                    m_copy["tool_calls"] = self._to_provider_tool_calls(tcs, is_groq)
                msgs.append(m_copy)
        else:
            msgs = []
            if system_content:
                msgs.append({'role': 'system', 'content': system_content})
            msgs.append({'role': 'user', 'content': prompt or ''})

        if self.provider == 'API':
            groq_kwargs: dict[str, Any] = {
                "model": model,
                "messages": msgs,
                "stream": True,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                **kwargs,
            }
            if tools:
                groq_kwargs["tools"] = tools
                groq_kwargs["tool_choice"] = "auto"

            stream = self.groq_client.chat.completions.create(**groq_kwargs)

            accumulated_tool_calls: dict[int, dict[str, str]] = {}

            for chunk in stream:
                if stream_cancel_event and stream_cancel_event.is_set():
                    yield {'type': 'aborted'}
                    return
                if chunk.choices:
                    delta = chunk.choices[0].delta

                    # Accumulate streaming tool_calls (Groq sends them incrementally)
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.id:
                                accumulated_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    accumulated_tool_calls[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

                    # Stream text content when available
                    if delta and delta.content:
                        text = delta.content
                        if cleaned_output:
                            text = self.clean(text)
                        yield {'type': 'chunk', 'content': text}
                        await asyncio.sleep(0.02)

            # After stream finishes, yield tool_calls_detected if any were accumulated
            if accumulated_tool_calls:
                normalized: list[dict[str, Any]] = []
                for idx in sorted(accumulated_tool_calls.keys()):
                    tc = accumulated_tool_calls[idx]
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError as ex:
                        log_error(str(ex), source="agent.py:llm_streaming(groq_args)")
                        args = {}
                    normalized.append({
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": args,
                    })
                yield {'type': 'tool_calls_detected', 'content': normalized}
        else:
            options = {}
            if temperature is not None:
                options['temperature'] = temperature
            if top_p is not None:
                options['top_p'] = top_p
            if max_tokens:
                options['num_predict'] = max_tokens
            for k in ('seed', 'num_ctx', 'top_k', 'min_p', 'repeat_penalty',
                      'frequency_penalty', 'presence_penalty', 'mirostat',
                      'mirostat_tau', 'mirostat_eta', 'typical_p', 'tfs_z',
                      'num_thread', 'num_gpu', 'stop'):
                if k in kwargs:
                    options[k] = kwargs.pop(k)
            stream = self.ollama_client.chat(
                model=model,
                messages=msgs,
                stream=True,
                tools=tools if tools else None,
                options=options,
            )
            accumulated_tool_calls: dict[int, dict[str, str]] = {}
            for chunk in stream:
                if stream_cancel_event and stream_cancel_event.is_set():
                    yield {'type': 'aborted'}
                    return
                if chunk.message and chunk.message.content:
                    text = chunk.message.content
                    if cleaned_output:
                        text = self.clean(text)
                    yield {'type': 'chunk', 'content': text}
                # Accumulate streaming tool_calls (Ollama sends them in chunks)
                if chunk.message and chunk.message.tool_calls:
                    for idx, tc in enumerate(chunk.message.tool_calls):
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                        # Ollama ToolCall may not have 'id' attribute
                        tc_id = getattr(tc, 'id', None)
                        if tc_id:
                            accumulated_tool_calls[idx]["id"] = tc_id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                # Ollama may send arguments as dict or string
                                args = tc.function.arguments
                                if isinstance(args, dict):
                                    args = json.dumps(args, ensure_ascii=False)
                                accumulated_tool_calls[idx]["arguments"] += args

            # After stream finishes, yield tool_calls_detected if any were accumulated
            if accumulated_tool_calls:
                normalized: list[dict[str, Any]] = []
                for idx in sorted(accumulated_tool_calls.keys()):
                    tc = accumulated_tool_calls[idx]
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError as ex:
                        log_error(str(ex), source="agent.py:llm_streaming(ollama_args)")
                        args = {}
                    normalized.append({
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": args,
                    })
                yield {'type': 'tool_calls_detected', 'content': normalized}

    
    def clean(self, text:str) -> str:
        '''
        Remove special Unicode characters and formatting artifacts from the provided text.

        The cleaning performed is deliberately conservative: it replaces zero-width and
        non-standard space characters, several dash variants and some invisible markers.

        ## Args:
            - text (str): Input text to clean.

        ## Returns:
            str: Cleaned text.

        ## Example:
            >>> agent.clean('Hello\\u200bWorld')
            'HelloWorld'
        '''
        text = text.replace('\ufeff', '')
        text = text.replace('\u202f', ' ')   # espacio fino -> espacio normal
        text = text.replace('\u2011', '-')   # guion no separable -> guion normal
        text = text.replace('\u2013', '-')   # guion en dash -> guion normal
        text = text.replace('\u2014', '-')   # guion em dash -> guion normal
        text = text.replace(chr(8209), '-')
        text = text.replace('\u200b', '')       
        return text
        
    def prompt(self, prompt_name: str) -> str:
        """Load a prompt file from the ``prompts/`` directory.

        Reads ``{current_dir}/prompts/{prompt_name}.md`` where
        ``current_dir`` is the directory of this file (``backend/agent/``).

        Args:
            prompt_name: Prompt file name (without ``.md`` extension).

        Returns:
            The file content as a string.

        Raises:
            FileNotFoundError: If the prompt file does not exist.
        """
        with open(f'{current_dir}/prompts/{prompt_name}.md', 'r', encoding='utf-8') as f:
            prompt = f.read()

        return prompt

    
if __name__ == '__main__': 
    print('Agent module for LLM interaction and various utilities.')