const http = require("node:http");
const { spawn } = require("node:child_process");
const { dirname, join } = require("node:path");

const rendererUrl = process.env.YAVERVOICE_RENDERER_URL || "http://127.0.0.1:5173";
const viteHost = new URL(rendererUrl).hostname || "127.0.0.1";
const electronExecutable = require("electron");
const viteCli = join(dirname(require.resolve("vite/package.json")), "bin", "vite.js");
const tscCli = join(dirname(require.resolve("typescript/package.json")), "bin", "tsc");

let shuttingDown = false;
let viteProcess = null;
let electronProcess = null;

function spawnNodeScript(scriptPath, args) {
  return spawn(process.execPath, [scriptPath, ...args], {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
    windowsHide: false
  });
}

function runNodeScript(scriptPath, args) {
  return new Promise((resolve) => {
    const child = spawnNodeScript(scriptPath, args);
    child.on("exit", (code, signal) => {
      resolve({ code: code ?? 0, signal });
    });
  });
}

function waitForRenderer(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;

  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(url, (response) => {
        response.resume();
        resolve();
      });

      request.on("error", () => {
        if (Date.now() >= deadline) {
          reject(new Error(`Renderer dev server did not start: ${url}`));
          return;
        }
        setTimeout(check, 250);
      });

      request.setTimeout(1000, () => {
        request.destroy();
      });
    };

    check();
  });
}

function stopChild(child) {
  return new Promise((resolve) => {
    if (!child || child.killed || child.exitCode !== null || child.signalCode !== null) {
      resolve();
      return;
    }

    const timeout = setTimeout(resolve, 2000);
    child.once("exit", () => {
      clearTimeout(timeout);
      resolve();
    });
    child.kill();
  });
}

async function shutdown(exitCode = 0) {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  await Promise.all([
    stopChild(electronProcess),
    stopChild(viteProcess)
  ]);
  process.exit(exitCode);
}

process.once("SIGINT", () => shutdown(0));
process.once("SIGTERM", () => shutdown(0));

async function main() {
  viteProcess = spawnNodeScript(viteCli, ["--host", viteHost]);
  viteProcess.on("exit", (code, signal) => {
    if (!shuttingDown) {
      console.error(`Vite exited with code ${code ?? "null"} signal ${signal ?? "null"}.`);
      shutdown(code || 1);
    }
  });

  await waitForRenderer(rendererUrl);

  const tscResult = await runNodeScript(tscCli, ["-p", "tsconfig.electron.json"]);
  if (tscResult.code !== 0) {
    shutdown(tscResult.code || 1);
    return;
  }

  electronProcess = spawn(electronExecutable, ["."], {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
    windowsHide: false
  });

  electronProcess.on("exit", (code, signal) => {
    shutdown(signal ? 0 : code ?? 0);
  });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  shutdown(1);
});
