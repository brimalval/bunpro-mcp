from __future__ import annotations

import os
import sys
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from typing import Callable, Final, cast

import importlib
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError, field_validator
from src.api_client import (
    reset_request_frontend_api_token,
    set_request_frontend_api_token,
)

from src.tools.vocabulary import register_vocab_tools


class ServerConfig(BaseModel):
    host: str = Field("127.0.0.1")
    port: int = Field(8000, ge=1, le=65535)
    stream_path: str = Field("/mcp")

    @field_validator("stream_path", mode="before")
    def ensure_leading_slash(cls, value: str) -> str:
        normalized = value.strip() or "/mcp"
        if not normalized.startswith("/"):
            normalized = f"/{normalized.lstrip('/')}"
        return normalized


def load_config() -> ServerConfig:
    _ = load_dotenv()
    try:
        try:
            port_value = int(os.environ.get("BUNPRO_PORT", "8000"))
        except ValueError as exc:
            raise RuntimeError("BUNPRO_PORT must be an integer") from exc

        return ServerConfig(
            host=os.environ.get("BUNPRO_HOST", "127.0.0.1"),
            port=port_value,
            stream_path=os.environ.get("BUNPRO_STREAM_PATH", "/mcp"),
        )
    except ValidationError as error:
        raise RuntimeError("Invalid Bunpro server configuration") from error


CONFIG: Final[ServerConfig] = load_config()


mcp: Final[FastMCP] = FastMCP(
    name="Bunpro MCP",
    instructions="Provides Bunpro grammar, vocabulary, and review data via streamable HTTP tools.",
    host=CONFIG.host,
    port=CONFIG.port,
    streamable_http_path=CONFIG.stream_path,
    stateless_http=True,
    log_level="INFO",
    json_response=True,
)


def _register_user_stats_tools(mcp: FastMCP) -> None:
    user_stats_module = importlib.import_module("src.tools.user_stats")
    register_fn = cast(
        Callable[[FastMCP], None],
        getattr(user_stats_module, "register_user_stats_tools"),
    )
    register_fn(mcp)


def _register_review_tools(mcp: FastMCP) -> None:
    review_module = importlib.import_module("src.tools.review")
    register_fn = cast(
        Callable[[FastMCP], None],
        getattr(review_module, "register_review_tools"),
    )
    register_fn(mcp)


def _register_reading_tools(mcp: FastMCP) -> None:
    reading_module = importlib.import_module("src.tools.reading")
    register_fn = cast(
        Callable[[FastMCP], None],
        getattr(reading_module, "register_reading_tools"),
    )
    register_fn(mcp)


def _register_grammar_tools(mcp: FastMCP) -> None:
    grammar_module = importlib.import_module("src.tools.grammar")
    register_fn = cast(
        Callable[[FastMCP], None],
        getattr(grammar_module, "register_grammar_tools"),
    )
    register_fn(mcp)


register_vocab_tools(mcp)
_register_reading_tools(mcp)
_register_grammar_tools(mcp)
_register_review_tools(mcp)
_register_user_stats_tools(mcp)

STREAMABLE_HTTP_APP = mcp.streamable_http_app()


def log_startup() -> None:
    print(
        (
            "Bunpro MCP streamable HTTP server starting at "
            f"http://{CONFIG.host}:{CONFIG.port}{CONFIG.stream_path}"
        ),
        file=sys.stderr,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log_startup()
    async with mcp.session_manager.run():
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bunpro MCP Streamable Gateway",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )

    async def frontend_api_token_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        token = set_request_frontend_api_token(
            request.cookies.get("frontend_api_token")
        )
        try:
            return await call_next(request)
        finally:
            reset_request_frontend_api_token(token)

    _ = app.middleware("http")(frontend_api_token_context)
    app.mount("/", STREAMABLE_HTTP_APP, name="bunpro-streamable-http")
    return app


app = create_app()


def main() -> None:
    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port, log_level="info")


if __name__ == "__main__":
    main()
