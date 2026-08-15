import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import net from "node:net";
import { dirname, resolve } from "node:path";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const frontendDirectory = resolve(scriptDirectory, "..");
const rootDirectory = resolve(frontendDirectory, "..");
const playwrightCli = resolve(frontendDirectory, "node_modules", "playwright", "cli.js");
const backendPython = process.platform === "win32"
  ? resolve(rootDirectory, "backend", ".venv", "Scripts", "python.exe")
  : resolve(rootDirectory, "backend", ".venv", "bin", "python");
const nextCli = resolve(frontendDirectory, "node_modules", "next", "dist", "bin", "next");
const servers = [
  {
    name: "backend",
    command: backendPython,
    args: ["backend/run.py"],
    cwd: rootDirectory,
    port: 8010,
    url: "http://127.0.0.1:8010/ready",
    timeoutMs: 30_000,
    stdio: "inherit",
    env: {
      ENVIRONMENT: "test",
      HOST: "127.0.0.1",
      PORT: "8010",
      FRONTEND_ORIGINS: "http://127.0.0.1:3100",
      DEMO_JOB_DURATION_SECONDS: "10",
    },
  },
  {
    name: "frontend",
    command: process.execPath,
    args: [nextCli, "dev", "--hostname", "127.0.0.1", "--port", "3100"],
    cwd: frontendDirectory,
    port: 3100,
    url: "http://127.0.0.1:3100",
    timeoutMs: 45_000,
    stdio: "inherit",
    env: {
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8010",
      NEXT_DIST_DIR: ".next-e2e",
    },
  },
];

const delay = (milliseconds) => new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
const playwrightTimeoutMs = Number(process.env.CATCH_UP_E2E_TIMEOUT_MS ?? 120_000);
const children = [];
let interrupted = false;
let requestedExitCode = null;
let cleanupPromise = null;

if (!Number.isFinite(playwrightTimeoutMs) || playwrightTimeoutMs <= 0) {
  throw new Error("CATCH_UP_E2E_TIMEOUT_MS must be a positive number.");
}

const processSnapshotScript = `
$ErrorActionPreference = "SilentlyContinue"
Get-Process | ForEach-Object {
  $parentId = $null
  try { $parentId = $_.Parent.Id } catch {}
  [PSCustomObject]@{ Id = $_.Id; ParentId = $parentId }
} | ConvertTo-Json -Compress
`;

function isPortListening(port) {
  return new Promise((resolveListening) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    const finish = (listening) => {
      socket.destroy();
      resolveListening(listening);
    };
    socket.setTimeout(250);
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.once("timeout", () => finish(false));
  });
}

function commandOutput(command, args) {
  return new Promise((resolveOutput) => {
    const child = spawn(command, args, { shell: false, windowsHide: true, stdio: ["ignore", "pipe", "ignore"] });
    let output = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.once("error", () => resolveOutput(""));
    child.once("exit", () => resolveOutput(output));
  });
}

async function captureOwnedDescendants(child) {
  if (process.platform !== "win32" || !child.pid || hasExited(child)) return [];
  const output = await commandOutput("pwsh.exe", [
    "-NoProfile",
    "-NonInteractive",
    "-Command",
    processSnapshotScript,
  ]);
  if (!output) return [];
  let snapshot;
  try {
    snapshot = JSON.parse(output);
  } catch {
    return [];
  }
  const rows = Array.isArray(snapshot) ? snapshot : [snapshot];
  const depths = new Map([[child.pid, 0]]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const row of rows) {
      const pid = Number(row.Id);
      const parentPid = Number(row.ParentId);
      if (pid && depths.has(parentPid) && !depths.has(pid)) {
        depths.set(pid, depths.get(parentPid) + 1);
        changed = true;
      }
    }
  }
  return [...depths.entries()]
    .filter(([pid]) => pid !== child.pid)
    .sort((left, right) => right[1] - left[1])
    .map(([pid]) => pid);
}

async function isHttpReady(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 500);
  try {
    const response = await fetch(url, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

function startProcess(definition) {
  const child = spawn(definition.command, definition.args, {
    cwd: definition.cwd,
    env: { ...process.env, ...definition.env },
    shell: false,
    detached: process.platform !== "win32",
    stdio: definition.stdio ?? "inherit",
    windowsHide: true,
  });
  child.definition = definition;
  child.startError = null;
  child.once("error", (error) => {
    child.startError = error;
  });
  return child;
}

async function waitForServer(child) {
  const { name, url, timeoutMs } = child.definition;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (interrupted) throw new Error("E2E startup was interrupted.");
    if (child.startError) throw new Error(`${name} could not start: ${child.startError.message}`);
    if (await isHttpReady(url)) {
      console.log(`[e2e] ${name} ready at ${url}`);
      return;
    }
    if (child.exitCode !== null || child.signalCode !== null) {
      throw new Error(`${name} exited before becoming ready (code ${child.exitCode ?? child.signalCode}).`);
    }
    await delay(100);
  }
  throw new Error(`${name} did not become ready at ${url} within ${timeoutMs}ms.`);
}

function hasExited(child) {
  return child.exitCode !== null || child.signalCode !== null;
}

function waitForExit(child, timeoutMs = null) {
  if (hasExited(child)) return Promise.resolve(true);
  return new Promise((resolveExit) => {
    let timer;
    const finish = (exited) => {
      clearTimeout(timer);
      child.off("exit", onExit);
      child.off("error", onError);
      resolveExit(exited);
    };
    const onExit = () => finish(true);
    const onError = () => finish(true);
    child.once("exit", onExit);
    child.once("error", onError);
    if (timeoutMs !== null) timer = setTimeout(() => finish(false), timeoutMs);
    if (hasExited(child)) finish(true);
  });
}

function sendUnixSignal(child, signal) {
  try {
    process.kill(-child.pid, signal);
  } catch {
    try {
      child.kill(signal);
    } catch {
      // The process may have exited between the checks and the signal.
    }
  }
}

function terminateOwnedPid(pid) {
  try {
    process.kill(pid, "SIGKILL");
  } catch {
    // The process may have exited between the snapshot and the cleanup pass.
  }
}

async function terminateTree(child) {
  if (!child || !child.pid || child.treeTerminationStarted) return;
  child.treeTerminationStarted = true;
  if (process.platform === "win32") {
    if (hasExited(child)) return;
    const ownedDescendants = await captureOwnedDescendants(child);
    if (hasExited(child)) return;
    for (const pid of ownedDescendants) terminateOwnedPid(pid);
    try {
      child.kill("SIGKILL");
    } catch {
      // The process may have exited between the snapshot and the signal.
    }
  } else {
    sendUnixSignal(child, "SIGTERM");
    if (!(await waitForExit(child, 5_000))) sendUnixSignal(child, "SIGKILL");
  }
  await waitForExit(child, 2_000);
}

async function waitForPortsToClose() {
  const deadline = Date.now() + 30_000;
  let occupied = [];
  do {
    occupied = [];
    for (const server of servers) {
      if (await isPortListening(server.port)) occupied.push(server.port);
    }
    if (!occupied.length) return [];
    await delay(100);
  } while (Date.now() < deadline);
  return occupied;
}

function runPlaywright() {
  return startProcess({
    name: "Playwright",
    command: process.execPath,
    args: [playwrightCli, "test", "--reporter=list", ...process.argv.slice(2)],
    cwd: frontendDirectory,
  });
}

async function cleanupOwnedProcesses() {
  await Promise.all([...children].reverse().map(terminateTree));
  const occupiedAfter = await waitForPortsToClose();
  if (occupiedAfter.length) {
    console.error(`[e2e] server cleanup failed; port(s) still in use: ${occupiedAfter.join(", ")}`);
    return false;
  }
  console.log("[e2e] server cleanup confirmed");
  return true;
}

function beginCleanup() {
  if (!cleanupPromise) {
    cleanupPromise = cleanupOwnedProcesses().catch((error) => {
      console.error(`[e2e] server cleanup failed: ${error instanceof Error ? error.message : String(error)}`);
      return false;
    });
  }
  return cleanupPromise;
}

async function main() {
  const occupiedBefore = [];
  for (const server of servers) {
    if (await isPortListening(server.port)) occupiedBefore.push(server.port);
  }
  if (occupiedBefore.length) {
    console.error(`[e2e] required port(s) already in use: ${occupiedBefore.join(", ")}`);
    return 2;
  }
  if (interrupted) return requestedExitCode ?? 1;

  let exitCode = 1;
  try {
    for (const definition of servers) children.push(startProcess(definition));
    for (const child of children) await waitForServer(child);
    if (interrupted) {
      exitCode = requestedExitCode ?? 1;
    } else {
      const playwright = runPlaywright();
      children.push(playwright);
      if (!(await waitForExit(playwright, playwrightTimeoutMs))) {
        throw new Error(`Playwright did not exit within ${playwrightTimeoutMs}ms.`);
      }
      exitCode = playwright.exitCode ?? 1;
    }
  } catch (error) {
    console.error(`[e2e] ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    const cleanupSucceeded = await beginCleanup();
    if (!cleanupSucceeded && exitCode === 0) exitCode = 2;
  }
  return requestedExitCode ?? exitCode;
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    if (interrupted) return;
    interrupted = true;
    requestedExitCode = signal === "SIGINT" ? 130 : 143;
    void beginCleanup();
  });
}

const exitCode = await main();
process.exit(exitCode);
