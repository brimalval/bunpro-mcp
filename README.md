# Bunpro MCP

## Overview
This FastAPI/uvicorn server exposes the Bunpro MCP bundle to other agents via HTTP streaming at `/mcp`. It registers grammar, vocabulary, reading, user statistics, and review tools that proxy Bunpro API endpoints.

This is a personal learning project built to:
- Explore how MCP (Model Context Protocol) servers work
- Assist with Japanese language study via Bunpro integration

Not affiliated with Bunpro. Built for educational purposes.

## Requirements
- Python 3.14 or later (matching Bunpro MCP dependencies)
- Astral's `uv` CLI. Install it via `pip install uv` or follow https://github.com/astral-sh/uv, then run `uv sync` from the repo root before starting the server.

## Setup
1. Copy `.env.example` to `.env` and supply your Bunpro frontend API token (`BUNPRO_FRONTEND_API_TOKEN=` line). Treat the token like any other secret; do not commit it.
2. If requests arrive through HTTP, the server first reads Bunpro's `frontend_api_token` cookie and uses that token for outbound Bunpro API calls.
3. For local runs without that cookie, the server falls back to `BUNPRO_FRONTEND_API_TOKEN`, then to legacy `BUNPRO_JWT`.

## Environment variables
- `BUNPRO_FRONTEND_API_TOKEN` (preferred): Bunpro frontend API token used by every tool when no request cookie is present.
- `BUNPRO_JWT` (legacy alias): backward-compatible fallback for `BUNPRO_FRONTEND_API_TOKEN`.
- `BUNPRO_API_BASE_URL` (optional): override the Bunpro API root (defaults to built-in client value).
- `BUNPRO_HOST` (optional): host the server listens on (defaults to `127.0.0.1`).
- `BUNPRO_PORT` (optional): port the server listens on (defaults to `8000`).
- `BUNPRO_STREAM_PATH` (optional): MCP stream path (defaults to `/mcp`).

## Running the server
From the repo root, run the FastAPI app with the frontend API token on the same line so the server picks it up immediately. `uv run` reuses the environment that `uv sync` prepared for this repo.

```
BUNPRO_FRONTEND_API_TOKEN=your_frontend_api_token_here uv run server.py
```

## Using OpenCode (MCP client)
[OpenCode](https://opencode.ai) can connect to this server as an MCP client. The server runs at `http://127.0.0.1:8000/mcp` by default.

### Setup
1. Install OpenCode (see [OpenCode docs](https://opencode.ai/docs))
2. Use `.env.example` to create a `.env` file with your Bunpro API token
3. Start the MCP server:
   ```bash
   uv --env-file .env run server.py
   ```
4. Configure OpenCode to connect to the server. Add to your `opencode.jsonc`:
   ```jsonc
   {
     "mcpServers": {
       "bunpro": {
         "url": "http://127.0.0.1:8000/mcp"
       }
     }
   }
   ```
5. Run `opencode` and start chatting with access to Bunpro tools

### Optional: Bunpro Tutor Agent
This repo includes a pre-configured agent at `.opencode/agent/bunpro-tutor.md` that provides Japanese tutoring assistance. To use it:
1. Ensure the `.opencode/` directory is in your project
2. In OpenCode, switch to the **bunpro-tutor** agent
3. Ask questions about your Japanese study progress

Example prompt:
```
I'm currently reviewing. Why is 行きませんか used instead of 行きましょうか here?
```

## Inspecting tools with MCP Inspector
Use the bundled MCP Inspector to list and invoke tools while the server is running:

```
BUNPRO_FRONTEND_API_TOKEN=your_frontend_api_token_here uv run mcp dev server.py
```

With the inspector running you can explore the registered tools, view their signatures, and pass arguments interactively from the UI.

## Tool reference + examples
Choose between the MCP Inspector and Python scripts for invoking tools. MCP Inspector exposes the registered tool list whenever you run `uv run mcp dev server.py`; you pick a tool name, fill its arguments, and send the request interactively. Automation or debugging can call the async tool functions directly with `uv run python`.

### Python snippets
Replace `your_frontend_api_token_here` with the value you exported (and keep it out of version control):

- `search_grammar(query)`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.grammar import search_grammar

  async def main():
      print(await search_grammar("particles"))

  asyncio.run(main())
  PY
  ```
- `get_grammar_point(slug)`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.grammar import get_grammar_point

  async def main():
      print(await get_grammar_point("particles-1"))

  asyncio.run(main())
  PY
  ```
- `get_vocab_level()`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.vocabulary import get_vocab_level

  async def main():
      print(await get_vocab_level())

  asyncio.run(main())
  PY
  ```
- `get_vocab_items(vocab_slug_or_id)`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.vocabulary import get_vocab_items

  async def main():
      print(await get_vocab_items("genki-lesson-1"))

  asyncio.run(main())
  PY
  ```
- `search_vocab(query, result_limit=None)`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.vocabulary import search_vocab

  async def main():
      print(await search_vocab("greetings", result_limit=10))

  asyncio.run(main())
  PY
  ```
- `get_reading_passages()`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.reading import get_reading_passages

  async def main():
      print(await get_reading_passages())

  asyncio.run(main())
  PY
  ```
- `search_reading_passages(query)`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.reading import search_reading_passages

  async def main():
      print(await search_reading_passages("vacation"))

  asyncio.run(main())
  PY
  ```
- `get_user_stats()`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.user_stats import get_user_stats

  async def main():
      print(await get_user_stats())

  asyncio.run(main())
  PY
  ```
- `get_jlpt_progress()`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.user_stats import get_jlpt_progress

  async def main():
      print(await get_jlpt_progress())

  asyncio.run(main())
  PY
  ```
- `get_srs_forecast(granularity="daily")`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.user_stats import get_srs_forecast

  async def main():
      print(await get_srs_forecast(granularity="daily"))

  asyncio.run(main())
  PY
  ```
- `get_study_configuration()`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.review import get_study_configuration

  async def main():
      print(await get_study_configuration())

  asyncio.run(main())
  PY
  ```
- `get_due_count()`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.review import get_due_count

  async def main():
      print(await get_due_count())

  asyncio.run(main())
  PY
  ```
- `get_pending_reviews()`
  ```bash
  uv run python - <<'PY'
  import asyncio
  from src.tools.review import get_pending_reviews

  async def main():
      print(await get_pending_reviews())

  asyncio.run(main())
  PY
  ```
