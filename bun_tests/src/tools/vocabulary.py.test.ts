// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../../_spawn";

test("src/tools/vocabulary.py imports", async () => {
  await spawnChecked([
    "uv",
    "run",
    "python",
    "-c",
    "import asyncio; from src.tools.vocabulary import search_vocab; print('ok')",
  ]);
});
