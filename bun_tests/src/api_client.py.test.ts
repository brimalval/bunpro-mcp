// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../_spawn";

test("src/api_client.py imports", async () => {
  await spawnChecked([
    "uv",
    "run",
    "python",
    "-c",
    "from src.api_client import BunproClient; print('ok')",
  ]);
});
