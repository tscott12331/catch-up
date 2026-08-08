import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const rootDirectory = resolve(scriptDirectory, "../..");
const backend = spawn("uv", ["run", "--project", "backend", "python", "backend/run.py"], {
  cwd: rootDirectory,
  env: process.env,
  stdio: "inherit",
});

function stopBackend(signal) {
  if (backend.exitCode === null && !backend.killed) backend.kill(signal);
}

process.once("SIGINT", () => stopBackend("SIGINT"));
process.once("SIGTERM", () => stopBackend("SIGTERM"));
backend.once("error", (error) => {
  console.error("Could not start the Playwright backend:", error);
  process.exitCode = 1;
});
backend.once("exit", (code, signal) => {
  if (signal) process.exitCode = 1;
  else process.exitCode = code ?? 1;
});
