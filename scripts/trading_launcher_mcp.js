#!/usr/bin/env node
// MCP server that launches and validates the Jarvis trading web UI.

const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const readline = require("readline");

const ROOT = process.env.JARVIS_ROOT || path.resolve(__dirname, "..");
const PYTHON = process.env.JARVIS_TRADING_PYTHON || "python";
const LOG_DIR = path.join(ROOT, "logs");
const LOG = path.join(LOG_DIR, "trading_web.log");

fs.mkdirSync(LOG_DIR, { recursive: true });

let flask = null;

function readLogTail(maxLines = 25) {
  try {
    const text = fs.readFileSync(LOG, "utf8");
    const lines = text.split(/\r?\n/).filter(Boolean);
    return lines.slice(-maxLines).join("\n") || "(log file is empty)";
  } catch (error) {
    if (error && error.code === "ENOENT") return "(log file not found)";
    return `(unable to read log: ${error && error.message ? error.message : String(error)})`;
  }
}

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function sendError(id, code, message, data) {
  const payload = { jsonrpc: "2.0", id, error: { code, message } };
  if (data) payload.error.data = data;
  send(payload);
}

function isAlive() {
  return !!(flask && flask.exitCode === null);
}

async function ensureFlask() {
  if (isAlive()) {
    return {
      ok: true,
      details: { status: "running", url: "http://127.0.0.1:5001", pid: flask.pid, logPath: LOG },
    };
  }

  const out = fs.openSync(LOG, "w");
  let spawnError = null;
  flask = spawn(PYTHON, [path.join(ROOT, "web", "trading_web.py")], {
    cwd: ROOT,
    stdio: ["ignore", out, out],
  });
  flask.once("error", (err) => {
    spawnError = err;
  });

  await new Promise((resolve) => setTimeout(resolve, 600));

  if (spawnError || !isAlive()) {
    return {
      ok: false,
      details: {
        status: "failed",
        exitCode: flask ? flask.exitCode : null,
        error: spawnError ? String(spawnError.message || spawnError) : null,
        logPath: LOG,
        logTail: readLogTail(),
      },
    };
  }

  return {
    ok: true,
    details: { status: "running", url: "http://127.0.0.1:5001", pid: flask.pid, logPath: LOG },
  };
}

function statusPayload() {
  if (isAlive()) {
    return { status: "running", url: "http://127.0.0.1:5001", pid: flask.pid, logPath: LOG };
  }
  if (!flask) {
    return { status: "stopped", logPath: LOG, logTail: readLogTail() };
  }
  return { status: "failed", exitCode: flask.exitCode, logPath: LOG, logTail: readLogTail() };
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on("line", async (line) => {
  if (!line.trim()) return;
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    return;
  }

  const { method, id } = msg;

  if (method === "initialize") {
    send({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "trading-launcher", version: "1.1.0" },
      },
    });
    return;
  }

  if (method === "notifications/initialized") {
    return;
  }

  if (method === "tools/list") {
    send({
      jsonrpc: "2.0",
      id,
      result: {
        tools: [
          {
            name: "trading_status",
            description: "Returns Jarvis Trading UI status and URL when healthy.",
            inputSchema: { type: "object", properties: {} },
          },
        ],
      },
    });
    return;
  }

  if (method === "tools/call") {
    const result = await ensureFlask();
    if (!result.ok) {
      sendError(id, -32000, "Trading UI failed to start", result.details);
      return;
    }

    send({
      jsonrpc: "2.0",
      id,
      result: {
        content: [
          { type: "text", text: "Trading UI is running at http://127.0.0.1:5001" },
          { type: "text", text: JSON.stringify(result.details) },
        ],
      },
    });
    return;
  }

  if (method === "trading/status") {
    send({ jsonrpc: "2.0", id, result: statusPayload() });
    return;
  }

  if (id !== undefined) {
    sendError(id, -32601, "Method not found");
  }
});
