import { promises as fs } from "node:fs";
import path from "node:path";

import { runDockerMission } from "./docker_runner.js";
import { normalizeOutput } from "./normalize.js";
import { ResearchArtifacts, ResearchMission } from "./types.js";

async function readPrompt(promptPath: string): Promise<string> {
  return fs.readFile(promptPath, "utf-8");
}

function buildMission(jobType: "finance" | "aiml", scope: "daily" | "weekly", topic: string, prompt: string): ResearchMission {
  return {
    jobType,
    scope,
    topic,
    requester: "jarvis",
    prompt,
  };
}

async function runMission(mission: ResearchMission): Promise<ResearchArtifacts> {
  const result = await runDockerMission(mission);
  if (result.exitCode !== 0) {
    throw new Error(`AI-Researcher Docker run failed with exit code ${result.exitCode}`);
  }
  const normalized = await normalizeOutput(mission, result.outputDir);
  return normalized.artifacts;
}

export async function runFinanceResearchJob(mission: ResearchMission): Promise<ResearchArtifacts> {
  return runMission(mission);
}

export async function runAIMLScanJob(mission: ResearchMission): Promise<ResearchArtifacts> {
  return runMission(mission);
}

export async function runWeeklyDeepDiveJob(mission: ResearchMission): Promise<ResearchArtifacts> {
  return runMission(mission);
}

export async function buildFinanceMission(topic: string): Promise<ResearchMission> {
  const promptPath = path.join(process.cwd(), "services", "researcher", "src", "prompts", "finance_daily.prompt.md");
  const prompt = await readPrompt(promptPath);
  return buildMission("finance", "daily", topic, prompt);
}

export async function buildAIMLMission(topic: string, scope: "daily" | "weekly"): Promise<ResearchMission> {
  const fileName = scope === "weekly" ? "aiml_weekly_deepdive.prompt.md" : "aiml_daily.prompt.md";
  const promptPath = path.join(process.cwd(), "services", "researcher", "src", "prompts", fileName);
  const prompt = await readPrompt(promptPath);
  return buildMission("aiml", scope, topic, prompt);
}
