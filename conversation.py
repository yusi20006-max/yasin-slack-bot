"""Bounded in-memory conversation history for YasinAI.

Conversation scope is isolated by Slack channel and, for threaded messages,
by the thread root timestamp. History is intentionally process-local.
"""

from collections import defaultdict, deque
from threading import RLock
from typing import Deque


class ConversationStore:
    """Store a bounded list of Gemini-compatible messages per conversation."""

    def __init__(self, max_messages: int = 12) -> None:
        if max_messages < 2:
            raise ValueError("max_messages must be at least 2")
        self.max_messages = max_messages
        self._history: dict[str, Deque[dict[str, str]]] = defaultdict(deque)
        self._lock = RLock()

    @staticmethod
    def key(channel_id: str, thread_ts: str | None = None) -> str:
        if not channel_id:
            raise ValueError("channel_id is required")
        return f"{channel_id}:thread:{thread_ts}" if thread_ts else f"{channel_id}:channel"

    def get(self, channel_id: str, thread_ts: str | None = None) -> list[dict[str, str]]:
        key = self.key(channel_id, thread_ts)
        with self._lock:
            return list(self._history[key])

    def append(
        self,
        channel_id: str,
        thread_ts: str | None,
        role: str,
        text: str,
    ) -> None:
        if role not in {"user", "model"}:
            raise ValueError("role must be user or model")
        if not text.strip():
            return

        key = self.key(channel_id, thread_ts)
        with self._lock:
            history = self._history[key]
            history.append({"role": role, "parts": [{"text": text.strip()}]})
            while len(history) > self.max_messages:
                history.popleft()

    def clear(self, channel_id: str, thread_ts: str | None = None) -> None:
        key = self.key(channel_id, thread_ts)
        with self._lock:
            self._history.pop(key, None)

    def size(self, channel_id: str, thread_ts: str | None = None) -> int:
        key = self.key(channel_id, thread_ts)
        with self._lock:
            return len(self._history[key])
