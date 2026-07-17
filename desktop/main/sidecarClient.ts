import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { EventEmitter } from "node:events";

type JsonRpcSuccess = {
  jsonrpc: "2.0";
  id: number;
  result: unknown;
};

type JsonRpcFailure = {
  jsonrpc: "2.0";
  id: number | null;
  error: {
    code: number;
    message: string;
  };
};

type JsonRpcNotification = {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, unknown>;
};

type PendingCall = {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
};

type SidecarClientOptions = {
  packaged?: boolean;
  resourcesPath?: string;
};

const SECRET_PATTERNS: Array<{ pattern: RegExp; keepPrefix: boolean }> = [
  { pattern: /gsk_[A-Za-z0-9_-]{8,}/g, keepPrefix: false },
  { pattern: /(GROQ_API_KEY\s*=\s*)\S+/gi, keepPrefix: true },
  { pattern: /(api[_-]?key["']?\s*[:=]\s*["']?)[^"',\s]+/gi, keepPrefix: true }
];

export class SidecarError extends Error {
  code?: number;

  constructor(message: string, code?: number) {
    super(message);
    this.name = "SidecarError";
    this.code = code;
  }
}

export class SidecarClient extends EventEmitter {
  private process?: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private pending = new Map<number, PendingCall>();
  private stdoutBuffer = "";
  private starting?: Promise<void>;
  private readonly packaged: boolean;
  private readonly resourcesPath?: string;

  constructor(private readonly projectRoot: string, options: SidecarClientOptions = {}) {
    super();
    this.packaged = Boolean(options.packaged);
    this.resourcesPath = options.resourcesPath;
  }

  async start(): Promise<void> {
    if (this.process && !this.process.killed) {
      return;
    }
    if (this.starting) {
      return this.starting;
    }

    this.starting = new Promise<void>((resolve, reject) => {
      const candidate = this.resolvePythonCommand();
      const child = spawn(candidate.command, candidate.args, {
        cwd: candidate.cwd,
        env: {
          ...process.env,
          PYTHONUTF8: "1",
          PYTHONIOENCODING: "utf-8"
        },
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true
      });

      let settled = false;
      const settleStart = () => {
        if (!settled) {
          settled = true;
          resolve();
        }
      };

      child.once("spawn", settleStart);
      child.once("error", (error) => {
        if (!settled) {
          settled = true;
          reject(error);
        }
        this.failPending(error);
      });
      child.once("exit", (code, signal) => {
        this.emit("log", {
          level: code === 0 ? "debug" : "error",
          message: `Sidecar exited with code ${code ?? "null"} signal ${signal ?? "null"}.`
        });
        this.failPending(new SidecarError("Sidecar process exited."));
        this.process = undefined;
      });

      child.stdout.setEncoding("utf8");
      child.stdout.on("data", (chunk: string) => this.handleStdout(chunk));

      child.stderr.setEncoding("utf8");
      child.stderr.on("data", (chunk: string) => {
        for (const rawLine of chunk.split(/\r?\n/)) {
          const line = rawLine.trim();
          if (line) {
            this.emit("log", { level: "debug", message: redactSecrets(line) });
          }
        }
      });

      this.process = child;
    }).finally(() => {
      this.starting = undefined;
    });

    return this.starting;
  }

  async invoke(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    await this.start();
    const child = this.process;
    if (!child || child.killed) {
      throw new SidecarError("Sidecar is not running.");
    }

    const id = this.nextId++;
    const payload = JSON.stringify({ jsonrpc: "2.0", id, method, params });

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      child.stdin.write(`${payload}\n`, "utf8", (error) => {
        if (error) {
          this.pending.delete(id);
          reject(error);
        }
      });
    });
  }

  async stop(gracePeriodMs = 1500): Promise<void> {
    const child = this.process;
    if (!child) {
      return;
    }

    this.failPending(new SidecarError("Sidecar stopped."));
    if (child.exitCode !== null || child.killed) {
      this.process = undefined;
      return;
    }

    await new Promise<void>((resolve) => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve();
      };
      const timer = setTimeout(() => {
        if (child.exitCode === null && !child.killed) child.kill();
        finish();
      }, gracePeriodMs);
      child.once("exit", finish);
      child.stdin.end();
    });
    if (this.process === child) this.process = undefined;
  }

  private handleStdout(chunk: string): void {
    this.stdoutBuffer += chunk;
    let newlineIndex = this.stdoutBuffer.indexOf("\n");

    while (newlineIndex >= 0) {
      const line = this.stdoutBuffer.slice(0, newlineIndex).trim();
      this.stdoutBuffer = this.stdoutBuffer.slice(newlineIndex + 1);
      if (line) {
        this.handleResponseLine(line);
      }
      newlineIndex = this.stdoutBuffer.indexOf("\n");
    }
  }

  private handleResponseLine(line: string): void {
    let response: JsonRpcSuccess | JsonRpcFailure | JsonRpcNotification;
    try {
      response = JSON.parse(line) as JsonRpcSuccess | JsonRpcFailure | JsonRpcNotification;
    } catch {
      this.emit("log", { level: "error", message: "Sidecar returned invalid JSON." });
      return;
    }

    if ("method" in response && typeof response.method === "string" && !("id" in response)) {
      this.emit("event", {
        method: response.method,
        params: response.params ?? {}
      });
      return;
    }

    if (!("id" in response) || typeof response.id !== "number") {
      this.emit("log", { level: "error", message: "Sidecar returned a response without a request id." });
      return;
    }

    const pending = this.pending.get(response.id);
    if (!pending) {
      return;
    }

    this.pending.delete(response.id);
    if ("error" in response) {
      pending.reject(new SidecarError(response.error.message, response.error.code));
    } else {
      pending.resolve(response.result);
    }
  }

  private resolvePythonCommand(): { command: string; args: string[]; cwd: string } {
    if (this.packaged) {
      const resourcesPath = this.resourcesPath;
      if (!resourcesPath) {
        throw new SidecarError("Packaged sidecar resources path was not provided.");
      }
      const executableName = process.platform === "win32" ? "YaverVoiceSidecar.exe" : "YaverVoiceSidecar";
      const executablePath = join(resourcesPath, "sidecar", executableName);
      if (!existsSync(executablePath)) {
        throw new SidecarError(`Bundled sidecar was not found at ${executablePath}.`);
      }
      return { command: executablePath, args: [], cwd: resourcesPath };
    }

    const windows = process.platform === "win32";
    const candidates = windows
      ? [
          { command: join(this.projectRoot, "venv", "Scripts", "python.exe"), args: ["-m", "src.sidecar"] },
          { command: join(this.projectRoot, ".venv", "Scripts", "python.exe"), args: ["-m", "src.sidecar"] },
          { command: "py", args: ["-m", "src.sidecar"] },
          { command: "python", args: ["-m", "src.sidecar"] }
        ]
      : [
          { command: join(this.projectRoot, ".venv", "bin", "python"), args: ["-m", "src.sidecar"] },
          { command: join(this.projectRoot, "venv", "bin", "python"), args: ["-m", "src.sidecar"] },
          { command: "python3", args: ["-m", "src.sidecar"] },
          { command: "python", args: ["-m", "src.sidecar"] }
        ];

    const candidate = candidates.find((item) => isExecutablePath(item.command)) ?? candidates[candidates.length - 1];
    return { ...candidate, cwd: this.projectRoot };
  }

  private failPending(error: Error): void {
    for (const pending of this.pending.values()) {
      pending.reject(error);
    }
    this.pending.clear();
  }
}

function isExecutablePath(command: string): boolean {
  if (!command.includes("/") && !command.includes("\\")) {
    return false;
  }
  return existsSync(command);
}

function redactSecrets(value: string): string {
  return SECRET_PATTERNS.reduce((text, { pattern, keepPrefix }) => {
    return text.replace(pattern, (match, prefix: string | undefined) => {
      return keepPrefix && prefix ? `${prefix}[redacted]` : "[redacted]";
    });
  }, value);
}
