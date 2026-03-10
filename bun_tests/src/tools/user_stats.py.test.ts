// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../../_spawn";

test("src/tools/user_stats.py imports", async () => {
  await spawnChecked([
    "uv",
    "run",
    "python",
    "-c",
    "import asyncio; from src.tools.user_stats import get_user_stats; print('ok')",
  ]);
});
