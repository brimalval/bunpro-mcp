// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../../_spawn";

test("src/tools/grammar.py imports", async () => {
  await spawnChecked([
    "uv",
    "run",
    "python",
    "-c",
    "import asyncio; from src.tools.grammar import search_grammar; print('ok')",
  ]);
});
