"""Let the call page switch which DSH session answers."""

import re
from pathlib import Path

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from .agent.stateless_llm.dsh_session_llm import DshSessionLLM, normalize_session_id
from .service_context import ServiceContext

_CONF_PATH = Path("conf.yaml")
_SESSION_VALUE = re.compile(r"session_id:\s*(?:'[^'\n]*'|\"[^\"\n]*\"|\S+)")


class SessionSwitchBody(BaseModel):
    """JSON body for switching the live call to another session."""

    session_id: str = Field(..., alias="sessionId")


def register_dsh_session_routes(router: APIRouter, context: ServiceContext) -> None:
    """Add the session read and switch endpoints.

    Args:
        router: Router that is registered before the frontend static mount.
        context: Shared service context whose agent speaks on the call.
    """

    @router.get("/api/dsh-session")
    async def read_dsh_session() -> JSONResponse:
        """Return the session id the call is using now."""
        llm = _live_llm(context)
        if llm is None:
            return JSONResponse({"error": "当前电话没有走会话接通"}, status_code=409)
        return JSONResponse({"sessionId": llm.session_id})

    @router.post("/api/dsh-session")
    async def switch_dsh_session(body: SessionSwitchBody) -> JSONResponse:
        """Point the live call at the pasted session and remember it."""
        llm = _live_llm(context)
        if llm is None:
            return JSONResponse({"error": "当前电话没有走会话接通"}, status_code=409)
        try:
            session_id = normalize_session_id(body.session_id)
            llm.set_session(session_id)
            _remember_session(context, session_id)
            saved = _write_conf_session(session_id)
        except ValueError:
            return JSONResponse(
                {"error": "会话 ID 格式不对。请粘贴完整的 session- 开头编号。"},
                status_code=400,
            )
        except OSError:
            logger.exception("Could not save the switched DSH session id")
            return JSONResponse(
                {
                    "sessionId": session_id,
                    "warning": "这次通话已接通，但没能写入配置。重启服务后会回到旧会话。",
                }
            )
        if not saved:
            return JSONResponse(
                {
                    "sessionId": session_id,
                    "warning": "这次通话已接通，配置里没找到会话那一行。重启服务后会回到旧会话。",
                }
            )
        return JSONResponse({"sessionId": session_id})


def _live_llm(context: ServiceContext) -> DshSessionLLM | None:
    """Return the session LLM shared by the call.

    Args:
        context: Service context created at startup.

    Returns:
        The live DSH session client, or None when this call uses another LLM.
    """
    agent = context.agent_engine
    llm = getattr(agent, "_llm", None)
    if isinstance(llm, DshSessionLLM):
        return llm
    return None


def _remember_session(context: ServiceContext, session_id: str) -> None:
    """Keep the in-memory config aligned with the live call.

    Args:
        context: Service context created at startup.
        session_id: Session id that was just accepted.
    """
    character = context.character_config
    if character is None:
        return
    block = character.agent_config.llm_configs.dsh_session_llm
    if block is not None:
        block.session_id = session_id


def _write_conf_session(session_id: str) -> bool:
    """Replace the DSH session id stored in conf.yaml.

    Args:
        session_id: Session id to store.

    Returns:
        True when the session line was updated.

    Raises:
        OSError: The config file could not be read or written.
    """
    text = _CONF_PATH.read_text(encoding="utf-8")
    marker = text.find("dsh_session_llm:")
    if marker < 0:
        return False
    window = text[marker:]
    match = _SESSION_VALUE.search(window)
    if match is None or window[: match.start()].count("\n") > 4:
        return False
    updated = (
        text[: marker + match.start()]
        + f"session_id: '{session_id}'"
        + text[marker + match.end() :]
    )
    _CONF_PATH.write_text(updated, encoding="utf-8")
    return True
