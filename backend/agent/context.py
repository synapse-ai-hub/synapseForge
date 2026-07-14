"""Context manager for the quotation agent.

Manages conversation context, token counting, and context compaction
for the agent loop.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context for the quotation agent.

    Handles token counting, context limits, and compaction to ensure
    the conversation stays within model limits.

    Attributes:
        max_context_tokens: Maximum tokens allowed in context (default: 4096)
        auto_compaction: Whether to auto-compact when context is full
        reserved_tokens: Tokens reserved for system prompt
    """

    def __init__(
        self,
        max_context_tokens: int = 4096,
        auto_compaction: bool = True,
        reserved_tokens: int = 512,
    ):
        self.max_context_tokens = max_context_tokens
        self.auto_compaction = auto_compaction
        self.reserved_tokens = reserved_tokens
        self._context: List[Dict[str, str]] = []
        self._token_count = 0

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the context.

        Args:
            role: The role of the message sender (user, assistant, system)
            content: The message content
        """
        message = {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        self._context.append(message)
        self._token_count += self._count_tokens(content)

        # Auto-compact if needed
        if self.auto_compaction and self._token_count > self.max_context_tokens - self.reserved_tokens:
            self._compact_context()

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text (approximate)."""
        # Approximate token counting: 1 token ≈ 4 characters for English
        return len(text) // 4

    def _compact_context(self) -> None:
        """Compact context by removing oldest messages."""
        # Keep system message and recent user/assistant messages
        system_messages = [m for m in self._context if m["role"] == "system"]
        recent_messages = self._context[-10:]  # Keep last 10 messages
        
        self._context = system_messages + recent_messages
        self._token_count = sum(self._count_tokens(m["content"]) for m in self._context)
        logger.info("Context compacted: %d messages, %d tokens", len(self._context), self._token_count)

    def get_context(self) -> List[Dict[str, str]]:
        """Get the current context."""
        return self._context.copy()

    def is_overflow(self) -> bool:
        """Check if context exceeds limits."""
        return self._token_count > self.max_context_tokens - self.reserved_tokens

    def count_messages_tokens(self, messages: List[Dict]) -> int:
        """Count the approximate token total of a list of message dicts.

        Each message dict may contain ``content``, ``tool_calls`` and
        ``tool_results`` keys. All present text is counted using the same
        heuristic as :meth:`_count_tokens` (``len(text) // 4``).

        Args:
            messages: List of message dicts as returned by
                ``SessionManager.load_messages``.

        Returns:
            The summed approximate token count across all messages.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "") or ""
            total += self._count_tokens(content)

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                try:
                    total += self._count_tokens(json.dumps(tool_calls, ensure_ascii=False))
                except (TypeError, ValueError) as e:
                    log_error(str(e), source="context.py:count_messages_tokens(tool_calls)")
                    total += self._count_tokens(str(tool_calls))

            tool_results = msg.get("tool_results")
            if tool_results:
                try:
                    total += self._count_tokens(json.dumps(tool_results, ensure_ascii=False))
                except (TypeError, ValueError) as e:
                    log_error(str(e), source="context.py:count_messages_tokens(tool_results)")
                    total += self._count_tokens(str(tool_results))

        return total

    def is_approaching_limit(self, total_tokens: int, threshold: float = 0.8) -> bool:
        """Check whether the token count is approaching the context limit.

        Args:
            total_tokens: Current token count of the conversation.
            threshold: Fraction of the available limit that triggers the
                warning (default 0.8 → 80 %).

        Returns:
            ``True`` if ``total_tokens`` is at or above
            ``(max_context_tokens - reserved_tokens) * threshold``.
        """
        available = self.max_context_tokens - self.reserved_tokens
        if available <= 0:
            return True
        return total_tokens >= available * threshold

    def clear(self) -> None:
        """Clear the context."""
        self._context = []
        self._token_count = 0

    def to_dict(self) -> Dict:
        """Convert context to dictionary."""
        return {
            "context": self._context,
            "token_count": self._token_count,
            "max_context_tokens": self.max_context_tokens,
            "auto_compaction": self.auto_compaction,
            "reserved_tokens": self.reserved_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ContextManager":
        """Create ContextManager from dictionary."""
        instance = cls(
            max_context_tokens=data.get("max_context_tokens", 4096),
            auto_compaction=data.get("auto_compaction", True),
            reserved_tokens=data.get("reserved_tokens", 512),
        )
        instance._context = data.get("context", [])
        instance._token_count = data.get("token_count", 0)
        return instance
