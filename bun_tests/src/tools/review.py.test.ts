// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../../_spawn";

test("src/tools/review.py imports", async () => {
  await spawnChecked([
    "uv",
    "run",
    "python",
    "-c",
    "import asyncio; from src.tools.review import get_review_queue; print('ok')",
  ]);
});
