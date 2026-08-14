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
    stdio: "ignore",
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
    stdio: "ignore",
    env: {
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8010",
      NEXT_DIST_DIR: ".next-e2e",
    },
  },
];

const delay = (milliseconds) => new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
let interrupted = false;

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

function startProcess(definition) {
  const child = spawn(definition.command, definition.args, {
    cwd: definition.cwd,
    env: { ...process.env, ...definition.env },
    shell: false,
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
  const { name, port, timeoutMs } = child.definition;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (interrupted) throw new Error("E2E startup was interrupted.");
    if (child.startError) throw new Error(`${name} could not start: ${child.startError.message}`);
    if (await isPortListening(port)) {
      console.log(`[e2e] ${name} ready on port ${port}`);
      return;
    }
    if (child.exitCode !== null) throw new Error(`${name} exited before becoming ready (code ${child.exitCode}).`);
    await delay(100);
  }
  throw new Error(`${name} did not become ready within ${timeoutMs}ms.`);
}

function waitForExit(child, timeoutMs) {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve(true);
  return new Promise((resolveExit) => {
    const timer = setTimeout(() => {
      child.off("exit", onExit);
      resolveExit(false);
    }, timeoutMs);
    const onExit = () => {
      clearTimeout(timer);
      resolveExit(true);
    };
    child.once("exit", onExit);
    if (child.exitCode !== null || child.signalCode !== null) onExit();
  });
}

async function terminateTree(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  if (process.platform === "win32") {
    const taskkill = spawn("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], {
      shell: false,
      stdio: "ignore",
      windowsHide: true,
    });
    if (!(await waitForExit(taskkill, 5_000))) taskkill.kill();
  } else {
    child.kill("SIGTERM");
    if (!(await waitForExit(child, 5_000))) child.kill("SIGKILL");
  }
  await waitForExit(child, 2_000);
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

async function terminateListeningServers() {
  if (process.platform !== "win32") return;
  const netstat = await commandOutput("netstat.exe", ["-ano", "-p", "tcp"]);
  const ownedPids = new Set();
  for (const server of servers) {
    const pattern = new RegExp(`^\\s*TCP\\s+127\\.0\\.0\\.1:${server.port}\\s+\\S+\\s+LISTENING\\s+(\\d+)\\s*$`, "mi");
    const match = netstat.match(pattern);
    if (match) ownedPids.add(match[1]);
  }
  for (const pid of ownedPids) {
    try {
      process.kill(Number(pid));
    } catch {
      // Fall through to the process-tree fallback below.
    }
    await delay(100);
    const taskkill = spawn("taskkill.exe", ["/PID", pid, "/T", "/F"], {
      shell: false,
      stdio: "ignore",
      windowsHide: true,
    });
    if (!(await waitForExit(taskkill, 5_000))) taskkill.kill();
  }
}

async function waitForPortsToClose() {
  const deadline = Date.now() + 15_000;
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
    env: { CATCH_UP_E2E_EXTERNAL_SERVERS: "1" },
  });
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

  const children = [];
  let exitCode = 1;
  try {
    for (const definition of servers) children.push(startProcess(definition));
    for (const child of children) await waitForServer(child);
    if (interrupted) {
      exitCode = process.exitCode ?? 1;
    } else {
      const playwright = runPlaywright();
      children.push(playwright);
      if (!(await waitForExit(playwright, 120_000))) throw new Error("Playwright did not exit within 120000ms.");
      exitCode = playwright.exitCode ?? 1;
    }
  } catch (error) {
    console.error(`[e2e] ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    await Promise.all(children.toReversed().map(terminateTree));
    await terminateListeningServers();
    const occupiedAfter = await waitForPortsToClose();
    if (occupiedAfter.length) {
      console.error(`[e2e] server cleanup failed; port(s) still in use: ${occupiedAfter.join(", ")}`);
      exitCode = exitCode || 2;
    } else {
      console.log("[e2e] server cleanup confirmed");
    }
  }
  return exitCode;
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    if (interrupted) return;
    interrupted = true;
    process.exitCode = signal === "SIGINT" ? 130 : 143;
  });
}

const exitCode = await main();
process.exit(exitCode);
