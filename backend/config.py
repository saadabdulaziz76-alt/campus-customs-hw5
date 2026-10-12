"""Model and MCP wiring for the Campus Customs agent team.

Two rules this module exists to enforce:

1. Every agent runs on **gpt-6-luna** through Portkey. Nothing picks its own model.
2. Every shop fact comes from the **MCP server**. There is no direct database
   access anywhere in `backend/` — the only path to `campus_customs_new.db` is
   through the tools in `mcp_server/server.py`.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

HERE = Path(__file__).resolve().parent
HW_ROOT = HERE.parent
MCP_CONFIG = HW_ROOT / ".mcp.json"

# The shop's .env may sit beside the homework or anywhere up the course folder.
for folder in (HW_ROOT, *HW_ROOT.parents[:5]):
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env", override=False)

MODEL_NAME = "gpt-6-luna"        # fixed for every agent, by assignment
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")
REQUEST_TIMEOUT = 90.0

# --- loop limits, so a confused agent cannot spend without bound -------------
MAX_REQUESTS_PER_AGENT = 8      # model calls inside one agent run
MAX_TOOL_CALLS_PER_AGENT = 12   # MCP calls inside one agent run
MAX_DELEGATION_DEPTH = 2        # Boss -> specialist -> peer, and no further
MAX_DELEGATIONS_PER_RUN = 8     # total specialist hand-offs for one ticket


def api_key_present() -> bool:
    """Whether a key is configured. Never returns or logs the key itself."""
    return bool(os.getenv("PORTKEY_API_KEY", "").strip())


def api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Put it in a .env in this folder or a parent.")
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """One shared gpt-6-luna client for the whole team.

    Responses API, not chat/completions: gpt-6-luna refuses function tools on
    /v1/chat/completions, and every agent here needs tools.
    """
    client = AsyncOpenAI(
        api_key=api_key(),
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
        timeout=REQUEST_TIMEOUT,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def _resolve(value: str) -> str:
    """Make a path from .mcp.json absolute, relative to the homework folder.

    The file stores relative paths so the repository runs on any machine that
    clones it; an absolute path is still honoured if someone prefers one.
    """
    path = Path(value)
    if path.is_absolute():
        return value
    # Deliberately not .resolve() — a virtualenv's bin/python is a symlink to the
    # base interpreter, and following it would launch the server outside the venv
    # where fastmcp is not installed.
    return str(HW_ROOT / path)


def mcp_command() -> dict:
    """The server entry from .mcp.json — the same one a client would use.

    If the server's own virtualenv is not present, fall back to whichever
    interpreter is running this process. That lets a grader install everything
    into one environment and still have the agents launch the MCP server.
    """
    cfg = json.loads(MCP_CONFIG.read_text())["mcpServers"]["campus-customs-backoffice"]
    command = _resolve(cfg["command"])
    if not Path(command).exists():
        command = sys.executable
    return {**cfg, "command": command, "args": [_resolve(a) for a in cfg["args"]]}


def build_mcp_toolset() -> MCPToolset:
    """The team's only route to shop data.

    Launched over stdio from the .mcp.json entry, so the agents talk to exactly
    the server that is registered — not to a copy of its logic.
    """
    cfg = mcp_command()
    return MCPToolset(Client(StdioTransport(command=cfg["command"], args=cfg["args"])))
