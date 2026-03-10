import { test } from "bun:test";

test("python pytest", async () => {
  const child = Bun.spawn({
    cmd: ["uv", "run", "pytest", "-q"],
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });

  const exitCode = await child.exited;

  if (exitCode !== 0) {
    throw new Error(`uv run pytest -q exited with ${exitCode}`);
  }
});
