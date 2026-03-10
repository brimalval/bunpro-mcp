// @ts-nocheck
import { test } from "bun:test";

import { spawnChecked } from "../../_spawn";

test("src/types model validates good and bad data", async () => {
  await spawnChecked([
    "uv",
    "run",
    "python",
    "-c",
    [
      "from pydantic import ValidationError",
      "from src.types.tools import ToolRequest",
      "ToolRequest.model_validate({'tool': 'demo', 'payload': {'x': 1}})",
      "try:",
      "    ToolRequest.model_validate({'payload': {'x': 1}})",
      "    raise RuntimeError('expected ValidationError for bad data')",
      "except ValidationError:",
      "    pass",
      "print('ok')",
    ].join("\n"),
  ]);
});
