"""RAG helpers — low-level logic for the knowledge base endpoints.

This module centralises the non-endpoint logic used by
``backend/routes/rag.py``: collection-name validation, file size limits and
the SSRF-protected URL fetching (DNS pinning, private-IP blocking, redirect
handling and response size caps).

Keeping this logic in ``utils`` (instead of inline in the route) follows the
project convention of separating helpers from endpoints.

Imported by ``backend/routes/rag.py``.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
import sys
from typing import Any
from urllib.parse import urljoin, urlparse

import httpcore
import httpx

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logger = logging.getLogger(__name__)

# Per-file size limit (50 MB, same as context_files).
MAX_BYTES = 50 * 1024 * 1024
# Maximum files per request (avoids resource exhaustion).
MAX_FILES = 20
# Maximum redirects when fetching a URL.
MAX_REDIRECTS = 5
# Maximum response size when fetching a URL (avoids memory DoS).
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

# Private / loopback / link-local / metadata networks blocked for SSRF.
_PRIVATE_NETS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


# ---------------------------------------------------------------------------
# DNS pinning transport (mitigates DNS rebinding / TOCTOU)
# ---------------------------------------------------------------------------


class _PinnedIPBackend(httpcore.AsyncNetworkBackend):
    """Network backend that pins TCP connections to pre-validated IPs.

    The host->IP map is shared and mutable so redirects to new hosts can be
    pinned as they are followed. TLS SNI still uses the original hostname
    because only the TCP connection target is overridden.
    """

    def __init__(
        self,
        pins: dict[str, str],
        backend: httpcore.AsyncNetworkBackend,
    ) -> None:
        """Initialize the pinned backend.

        Args:
            pins: Mutable mapping ``hostname -> ip`` used to override the
                connection target.
            backend: Underlying network backend used for the real connection.
        """
        self._pins = pins
        self._backend = backend

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> Any:
        """Connect to the pinned IP for ``host`` when available.

        Args:
            host: Hostname to connect to.
            port: Remote port.
            timeout: Connection timeout.
            local_address: Optional local bind address.
            socket_options: Optional socket options.

        Returns:
            The network stream from the underlying backend.
        """
        pinned = self._pins.get(host, host)
        return await self._backend.connect_tcp(
            pinned, port, timeout, local_address, socket_options
        )

    def connect_unix_socket(self, path: str, timeout: float | None = None, socket_options: Any = None) -> Any:
        """Connect to a Unix socket via the underlying backend.

        Args:
            path: Socket path.
            timeout: Connection timeout.
            socket_options: Optional socket options.

        Returns:
            The network stream from the underlying backend.
        """
        return self._backend.connect_unix_socket(path, timeout, socket_options)

    async def sleep(self, seconds: float) -> None:
        """Delegate sleep to the underlying backend.

        Args:
            seconds: Seconds to sleep.
        """
        return await self._backend.sleep(seconds)


class _PinnedIPTransport(httpx.AsyncHTTPTransport):
    """Async HTTP transport whose connections are pinned to validated IPs."""

    def __init__(self, pins: dict[str, str], **kwargs: Any) -> None:
        """Initialize the transport with a shared pin map.

        Args:
            pins: Mutable mapping ``hostname -> ip`` used to override the
                connection target.
            **kwargs: Extra arguments forwarded to ``AsyncHTTPTransport``.
        """
        super().__init__(**kwargs)
        self._pool._network_backend = _PinnedIPBackend(pins, self._pool._network_backend)


def validar_nombre_coleccion(name: str) -> str | None:
    """Validate a collection name.

    Args:
        name: Name to validate.

    Returns:
        An error message, or ``None`` if the name is valid.
    """
    if not name:
        return "El nombre de la colección es obligatorio."
    if " " in name:
        return "El nombre de la colección no debe contener espacios."
    if name != name.lower():
        return "El nombre de la colección debe estar todo en minúscula."
    if not re.match(r"^[a-z0-9-]+$", name):
        return "Solo se permiten minúsculas, números y guiones."
    if len(name) < 3:
        return "El nombre de la colección debe tener al menos 3 caracteres."
    if name.startswith(("-", ".")) or name.endswith(("-", ".")):
        return "El nombre de la colección no puede empezar ni terminar con guión o punto."
    return None


def _is_private_ip(ip_str: str) -> bool:
    """Return ``True`` if an IP is private/loopback/link-local/metadata.

    Args:
        ip_str: IP address (IPv4 or IPv6).

    Returns:
        ``True`` if the IP belongs to a blocked network.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    # Normalize IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) to IPv4 to avoid
    # an SSRF bypass.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip in net for net in _PRIVATE_NETS)


def _validate_url(url: str) -> str:
    """Validate a URL scheme and hostname presence.

    Args:
        url: URL to validate.

    Returns:
        The normalized URL.

    Raises:
        ValueError: If the scheme is not http/https or the hostname is missing.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Solo se permiten URLs http/https.")
    if not parsed.hostname:
        raise ValueError("La URL es inválida.")
    return url


def _pin_host(url: str, pins: dict[str, str]) -> str:
    """Resolve a URL host, block private IPs and pin it in the map.

    Args:
        url: URL whose host must be resolved and pinned.
        pins: Mutable mapping ``hostname -> ip`` updated in place.

    Returns:
        The same URL.

    Raises:
        ValueError: If the host cannot be resolved or resolves to a private IP.
    """
    hostname = urlparse(url).hostname or ""
    infos = socket.getaddrinfo(hostname, None)
    public_ips: list[str] = []
    for info in infos:
        ip = info[4][0]
        if _is_private_ip(ip):
            raise ValueError("No se permiten URLs a direcciones internas.")
        public_ips.append(ip)
    if not public_ips:
        raise ValueError("No se pudo resolver el host de la URL.")
    pins[hostname] = public_ips[0]
    return url


async def fetch_url_content(url: str) -> tuple[str, str]:
    """Fetch a URL and return ``(text, html)`` with SSRF protection.

    Resolves and validates the initial URL and every redirect, blocking
    private addresses, and pins each connection to the validated IP to
    mitigate DNS rebinding.

    Args:
        url: URL to fetch.

    Returns:
        A tuple with the markdown text and the raw HTML.

    Raises:
        ValueError: If the URL is invalid, internal, too large or has too many
            redirects.
        httpx.HTTPError: If the fetch fails.
    """
    current = _validate_url(url)
    pins: dict[str, str] = {}
    transport = _PinnedIPTransport(pins)
    async with httpx.AsyncClient(
        timeout=30, follow_redirects=False, transport=transport
    ) as client:
        for _ in range(MAX_REDIRECTS):
            _pin_host(current, pins)
            resp = await client.get(
                current, headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                # Resolve the redirect (it may be relative) and re-validate.
                current = _validate_url(urljoin(current, str(resp.headers["location"])))
                continue
            resp.raise_for_status()
            # Read the response with a size limit to avoid memory DoS.
            content = b""
            async for chunk in resp.aiter_bytes():
                content += chunk
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ValueError("La respuesta de la URL es demasiado grande.")
            html = content.decode("utf-8", errors="replace")
            break
        else:
            raise ValueError("Demasiadas redirecciones al fetchear la URL.")

    try:
        import html2text

        converter = html2text.HTML2Text()
        converter.body_width = 0
        text = converter.handle(html)
    except ImportError:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

    return text, html