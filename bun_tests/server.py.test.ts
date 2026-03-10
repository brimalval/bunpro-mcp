// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "./_spawn";

test("server.py compiles", async () => {
  await spawnChecked([
    "uv",
    "run",
    "env",
    "BUNPRO_FRONTEND_API_TOKEN=dummy",
    "python",
    "-m",
    "py_compile",
    "server.py",
  ]);
});
