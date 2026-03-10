// @ts-nocheck
export async function spawnChecked(cmd: string[]): Promise<void> {
  const child = Bun.spawn({
    cmd,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });

  const exitCode = await child.exited;
  if (exitCode !== 0) {
    throw new Error(`${cmd.join(" ")} exited with ${exitCode}`);
  }
}
