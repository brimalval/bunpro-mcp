// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../_spawn";

test("tests/ runs pytest", async () => {
  await spawnChecked(["uv", "run", "pytest", "-q"]);
});
