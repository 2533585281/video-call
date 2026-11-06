"""Send each phone turn to an existing DSH session and speak its reply."""

import asyncio
import json
import re
import shutil
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from .stateless_llm_interface import StatelessLLMInterface

_TURN_SCRIPT = r"D:\DPH\video-call\tools\dsh_turn.mjs"
_TIMEOUT_SECONDS = 120
_SESSION_ID = re.compile(
    r"^session-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class DshSessionLLM(StatelessLLMInterface):
    """LLM that forwards the latest user turn into one DSH session.

    The session keeps its own persona, memory, and history. This class does
    not send the VTuber persona prompt.
    """

    def __init__(self, session_id: str, base_url: str | None = None) -> None:
        """Store the session this call is bound to.

        Args:
            session_id: DSH session id, including the ``session-`` prefix.
            base_url: DSH web API origin. Empty uses the script default.
        """
        if not session_id:
            raise ValueError("dsh_session_llm requires session_id")
        self.session_id = normalize_session_id(session_id)
        self.base_url = base_url or ""
        logger.info(f"DSH session call bound to {self.session_id}")

    def set_session(self, session_id: str) -> str:
        """Point later turns at another DSH session.

        Args:
            session_id: DSH session id, including the ``session-`` prefix.

        Returns:
            The stored session id.

        Raises:
            ValueError: The id is not a full ``session-`` UUID.
        """
        self.session_id = normalize_session_id(session_id)
        logger.info(f"DSH session call switched to {self.session_id}")
        return self.session_id

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """Forward the latest user turn and yield the session's reply.

        Args:
            messages: Chat messages. Only the last user turn is sent.
            system: Ignored. The session already has its own instructions.
            tools: Ignored. Tools stay inside the DSH session.

        Yields:
            The full reply text, as one chunk.

        Raises:
            RuntimeError: The turn script failed or returned no text.
        """
        del system, tools
        text, images = _latest_user_turn(messages)
        if not text and not images:
            raise RuntimeError("Nothing to send to the DSH session")
        reply = await _ask_session(self.session_id, self.base_url, text, images)
        if not reply.strip():
            raise RuntimeError("DSH session returned an empty reply")
        yield reply


def normalize_session_id(session_id: str) -> str:
    """Check that a pasted session id is a complete DSH id.

    Args:
        session_id: Raw text from the page or the config file.

    Returns:
        The id with surrounding spaces removed.

    Raises:
        ValueError: The text is empty or not a ``session-`` UUID.
    """
    cleaned = (session_id or "").strip()
    if not _SESSION_ID.fullmatch(cleaned):
        raise ValueError("session id must look like session-<uuid>")
    return cleaned


def _latest_user_turn(messages: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Take the text and image data URLs from the newest user message.

    Args:
        messages: Messages prepared by the agent.

    Returns:
        The spoken or typed text, and any ``data:image`` URLs.
    """
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content, []
        texts: list[str] = []
        images: list[str] = []
        for part in content or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                texts.append(str(part.get("text") or ""))
            elif part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url") or ""
                if isinstance(url, str) and url.startswith("data:image"):
                    images.append(url)
        return "\n".join(item for item in texts if item).strip(), images
    return "", []


async def _ask_session(
    session_id: str, base_url: str, text: str, images: list[str]
) -> str:
    """Run one DSH turn and return the assistant text.

    Args:
        session_id: Session that should answer.
        base_url: DSH origin. Empty lets the script choose.
        text: What the person on the phone said.
        images: Camera frames as data URLs.

    Returns:
        The assistant text from the finished turn.

    Raises:
        RuntimeError: Node is missing, the script failed, or it timed out.
    """
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is not installed")
    payload = json.dumps(
        {
            "sessionId": session_id,
            "baseUrl": base_url,
            "text": text,
            "images": images,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    process = await asyncio.create_subprocess_exec(
        node,
        _TURN_SCRIPT,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(payload), timeout=_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        raise RuntimeError("DSH session timed out") from exc
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "DSH session turn failed")
    return stdout.decode("utf-8").strip()
