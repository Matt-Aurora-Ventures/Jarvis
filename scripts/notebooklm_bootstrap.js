#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { Client } = require("@modelcontextprotocol/sdk/client");
const { StdioClientTransport } = require("@modelcontextprotocol/sdk/client/stdio.js");

function parseArgs(argv) {
  const out = {
    url: "",
    name: "Jarvis Architecture Notebook",
    tags: ["jarvis", "solana", "execution", "security"],
    setupAuth: false,
    question: "",
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--url" && argv[i + 1]) {
      out.url = argv[++i];
    } else if (arg === "--name" && argv[i + 1]) {
      out.name = argv[++i];
    } else if (arg === "--tags" && argv[i + 1]) {
      out.tags = argv[++i].split(",").map((x) => x.trim()).filter(Boolean);
    } else if (arg === "--setup-auth") {
      out.setupAuth = true;
    } else if (arg === "--question" && argv[i + 1]) {
      out.question = argv[++i];
    }
  }
  return out;
}

function parseToolPayload(result) {
  const textBlock = (result.content || []).find((item) => item.type === "text");
  if (!textBlock) {
    return { raw: result };
  }
  try {
    return JSON.parse(textBlock.text);
  } catch {
    return { raw_text: textBlock.text };
  }
}

function pickField(properties, preferredKeys) {
  for (const key of preferredKeys) {
    if (Object.prototype.hasOwnProperty.call(properties, key)) {
      return key;
    }
  }
  return null;
}

function buildAddNotebookArgs(schema, cfg) {
  const properties = (schema && schema.properties) || {};
  const args = {};

  const urlKey = pickField(properties, ["url", "notebook_url", "notebookUrl", "link"]);
  if (!urlKey) {
    throw new Error("add_notebook schema has no URL field");
  }
  args[urlKey] = cfg.url;

  const nameKey = pickField(properties, ["name", "title", "notebook_name"]);
  if (nameKey && cfg.name) {
    args[nameKey] = cfg.name;
  }

  const topicsKey = pickField(properties, ["topics"]);
  if (topicsKey && Array.isArray(cfg.tags) && cfg.tags.length > 0) {
    args[topicsKey] = cfg.tags;
  }

  const tagsKey = pickField(properties, ["tags"]);
  if (tagsKey && Array.isArray(cfg.tags) && cfg.tags.length > 0) {
    args[tagsKey] = cfg.tags;
  }

  const descKey = pickField(properties, ["description", "summary", "notes"]);
  if (descKey) {
    args[descKey] = "NotebookLM source for Jarvis architecture decisions and implementation context.";
  }

  const contentTypesKey = pickField(properties, ["content_types"]);
  if (contentTypesKey) {
    args[contentTypesKey] = ["documentation", "architecture", "execution"];
  }

  const useCasesKey = pickField(properties, ["use_cases"]);
  if (useCasesKey) {
    args[useCasesKey] = [
      "Architecture verification before coding",
      "Execution and signer hardening decisions",
      "Security boundary validation",
    ];
  }

  return args;
}

async function callTool(client, name, args) {
  const raw = await client.callTool({ name, arguments: args || {} });
  return parseToolPayload(raw);
}

function normalizeLibraryTopics() {
  const libPath = path.join(process.env.LOCALAPPDATA || "", "notebooklm-mcp", "Data", "library.json");
  if (!libPath || !fs.existsSync(libPath)) {
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(libPath, "utf8"));
  } catch {
    return;
  }
  if (!Array.isArray(parsed.notebooks)) {
    return;
  }
  let changed = false;
  for (const notebook of parsed.notebooks) {
    if (!Array.isArray(notebook.topics) || notebook.topics.length === 0) {
      const tags = Array.isArray(notebook.tags) ? notebook.tags : [];
      notebook.topics = tags.length > 0 ? tags : ["general"];
      changed = true;
    }
  }
  if (changed) {
    fs.writeFileSync(libPath, JSON.stringify(parsed, null, 2), "utf8");
  }
}

async function main() {
  const cfg = parseArgs(process.argv.slice(2));
  if (!cfg.url) {
    console.error("Usage: node scripts/notebooklm_bootstrap.js --url <notebook_link> [--setup-auth] [--name ...] [--tags a,b]");
    process.exit(1);
  }

  normalizeLibraryTopics();

  const transport = new StdioClientTransport({
    command: "node",
    args: ["node_modules/notebooklm-mcp/dist/index.js"],
    stderr: "pipe",
  });

  const stderrLines = [];
  if (transport.stderr) {
    transport.stderr.on("data", (chunk) => {
      const text = String(chunk);
      stderrLines.push(text.trim());
      if (stderrLines.length > 50) {
        stderrLines.shift();
      }
    });
  }

  const client = new Client({ name: "jarvis-notebooklm-bootstrap", version: "1.0.0" }, { capabilities: {} });

  try {
    await client.connect(transport);
    const tools = await client.listTools();
    const addTool = tools.tools.find((tool) => tool.name === "add_notebook");
    const selectTool = tools.tools.find((tool) => tool.name === "select_notebook");
    if (!addTool) {
      throw new Error("add_notebook tool not exposed by notebooklm-mcp");
    }

    const healthBefore = await callTool(client, "get_health", {});
    if (!healthBefore.authenticated && cfg.setupAuth) {
      await callTool(client, "setup_auth", {});
    }

    const initialList = await callTool(client, "list_notebooks", {});
    const initialNotebooks = initialList.notebooks || initialList.data?.notebooks || [];
    const existingByUrl = initialNotebooks.find((n) => n.url === cfg.url);

    const addArgs = buildAddNotebookArgs(addTool.inputSchema, cfg);
    const addResult = existingByUrl
      ? { success: true, data: { notebook: existingByUrl }, skipped: "already_exists" }
      : await callTool(client, "add_notebook", addArgs);

    normalizeLibraryTopics();
    const listResult = await callTool(client, "list_notebooks", {});

    let selected = null;
    const notebooks = listResult.notebooks || listResult.data?.notebooks || [];
    const addedId = addResult?.data?.notebook?.id;
    const match = notebooks.find((n) => n.url === cfg.url);
    const notebookId = addedId || (match && match.id);
    if (notebookId) {
      const selectProps = (selectTool && selectTool.inputSchema && selectTool.inputSchema.properties) || {};
      const selectKey = pickField(selectProps, ["notebook_id", "id", "notebookId"]) || "notebook_id";
      selected = await callTool(client, "select_notebook", { [selectKey]: notebookId });
    }

    let questionResult = null;
    if (cfg.question) {
      questionResult = await callTool(client, "ask_question", { question: cfg.question });
    }

    const healthAfter = await callTool(client, "get_health", {});
    console.log(
      JSON.stringify(
        {
          success: true,
          add_args: addArgs,
          add_result: addResult,
          selected,
          notebook_count: notebooks.length,
          health_before: healthBefore,
          health_after: healthAfter,
          question_result: questionResult,
        },
        null,
        2
      )
    );
  } catch (err) {
    const tail = stderrLines.slice(-10).join(" | ");
    throw new Error(`${String(err)} :: stderr_tail=${tail}`);
  } finally {
    await client.close();
    await transport.close();
  }
}

main().catch((err) => {
  const payload = { success: false, error: String(err) };
  console.error(JSON.stringify(payload, null, 2));
  process.exit(1);
});
