// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../../_spawn";

test("src/tools/reading.py imports", async () => {
  await spawnChecked([
    "uv",
    "run",
    "python",
    "-c",
    "import asyncio; from src.tools.reading import get_reading_passages; print('ok')",
  ]);
});
