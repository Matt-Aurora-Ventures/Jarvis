#!/usr/bin/env node
/**
 * Seed Supermemory with local markdown memory files.
 *
 * Motivation: Supermemory's API may block some HTTP clients (e.g. Python urllib)
 * with 403 HTML responses. Node's fetch + the same integrity headers used by the
 * official Clawdbot Supermemory plugin are much more reliable.
 *
 * Sources (if they exist):
 * - /root/clawd/MEMORY.md
 * - /root/clawd/memory/*.md
 * - /root/.clawdbot/MEMORY.md
 * - /root/.clawdbot/memory/*.md
 *
 * Env:
 * - SUPERMEMORY_API_KEY (preferred) or SUPERMEMORY_CLAWDBOT_API_KEY
 * - BOT_NAME
 * - SUPERMEMORY_CONTAINER_TAG (defaults to kr8tiv_<bot>)
 */

import { createHash, createHmac } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

const API_BASE = "https://api.supermemory.ai";

// Matches the HMAC key/version used by @supermemory/clawdbot-supermemory.
const INTEGRITY_VERSION = 1;
const INTEGRITY_HMAC_KEY =
  "7f2a9c4b8e1d6f3a5c0b9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a";

function sha256Hex(text) {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

function base64UrlNoPad(buf) {
  return buf
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function integrityHeaders(apiKey, containerTag) {
  const apiHash = sha256Hex(apiKey);
  const tagHash = sha256Hex(containerTag);
  const msg = `${apiHash}:${tagHash}:${INTEGRITY_VERSION}`;
  const sig = createHmac("sha256", INTEGRITY_HMAC_KEY).update(msg, "utf8").digest();
  return {
    "X-Content-Hash": tagHash,
    "X-Request-Integrity": `v${INTEGRITY_VERSION}.${base64UrlNoPad(sig)}`,
  };
}

async function existsFile(p) {
  try {
    const st = await fs.stat(p);
    return st.isFile();
  } catch {
    return false;
  }
}

async function listMd(dir) {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    return entries
      .filter((e) => e.isFile() && e.name.toLowerCase().endsWith(".md"))
      .map((e) => path.join(dir, e.name))
      .sort();
  } catch {
    return [];
  }
}

function seedCustomId(containerTag, filePath) {
  const h = createHash("sha256")
    .update(`${containerTag}:${filePath}`, "utf8")
    .digest("hex")
    .slice(0, 24);
  return `seed_${h}`;
}

async function postJson(url, headers, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      ...headers,
      "Content-Type": "application/json",
      Accept: "application/json",
      "User-Agent": "kr8tiv-supermemory-seed/1.0",
    },
    body: JSON.stringify(payload),
  });

  const body = await resp.text();
  return { status: resp.status, body };
}

async function main() {
  const apiKey =
    process.env.SUPERMEMORY_API_KEY || process.env.SUPERMEMORY_CLAWDBOT_API_KEY || "";
  if (!apiKey) {
    console.log("[supermemory-seed] SUPERMEMORY_API_KEY not set; skipping");
    return 0;
  }

  const botName = (process.env.BOT_NAME || "unknown").trim().toLowerCase();
  const privateTag = (process.env.SUPERMEMORY_CONTAINER_TAG || `kr8tiv_${botName}`)
    .trim()
    .toLowerCase();

  const sources = [];
  for (const root of ["/root/clawd", "/root/.clawdbot"]) {
    const mem = path.join(root, "MEMORY.md");
    if (await existsFile(mem)) sources.push(mem);
    sources.push(...(await listMd(path.join(root, "memory"))));
  }

  if (sources.length === 0) {
    console.log("[supermemory-seed] no local memory markdown found; nothing to seed");
    return 0;
  }

  const headers = {
    Authorization: `Bearer ${apiKey}`,
    ...integrityHeaders(apiKey, privateTag),
  };

  let ok = 0;
  let fail = 0;

  for (const p of sources) {
    let content = "";
    try {
      content = await fs.readFile(p, "utf8");
    } catch (e) {
      fail++;
      console.log(`[supermemory-seed] read failed: ${p}: ${String(e)}`);
      continue;
    }

    if (!content.trim()) continue;

    const payload = {
      content,
      containerTag: privateTag,
      customId: seedCustomId(privateTag, p),
      metadata: {
        source: "disk_seed",
        bot: botName,
        path: p,
        kind: "markdown_memory",
        seeded_at: new Date().toISOString(),
      },
    };

    try {
      const { status, body } = await postJson(`${API_BASE}/v3/documents`, headers, payload);
      if (status >= 200 && status < 300) {
        ok++;
        continue;
      }

      fail++;
      const preview = String(body || "").replace(/\s+/g, " ").slice(0, 240);
      console.log(`[supermemory-seed] upload failed: ${p} status=${status} body=${preview}`);
    } catch (e) {
      fail++;
      console.log(`[supermemory-seed] upload failed: ${p}: ${String(e)}`);
    }
  }

  console.log(`[supermemory-seed] done: ok=${ok} fail=${fail} tag=${privateTag}`);
  return fail === 0 ? 0 : 1;
}

main()
  .then((code) => process.exit(code))
  .catch((e) => {
    console.error(String(e));
    process.exit(1);
  });

