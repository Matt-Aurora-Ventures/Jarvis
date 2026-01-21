import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";

import { ResearchMission } from "./types.js";

export interface DockerRunResult {
  outputDir: string;
  exitCode: number;
}

export interface DockerRunnerConfig {
  image: string;
  outputRoot: string;
  env: Record<string, string>;
}

function assertDefined(value: string | undefined, label: string): string {
  if (!value) {
    throw new Error(`Missing required env var: ${label}`);
  }
  return value;
}

export function loadDockerConfig(): DockerRunnerConfig {
  const image = assertDefined(process.env.AI_RESEARCHER_IMAGE, "AI_RESEARCHER_IMAGE");
  const outputRoot = assertDefined(process.env.AI_RESEARCHER_OUTPUT_DIR, "AI_RESEARCHER_OUTPUT_DIR");
  const env: Record<string, string> = {};
  for (const key of Object.keys(process.env)) {
    if (key.startsWith("AI_RESEARCHER_")) {
      const value = process.env[key];
      if (value) {
        env[key] = value;
      }
    }
  }
  return { image, outputRoot, env };
}

export async function runDockerMission(mission: ResearchMission): Promise<DockerRunResult> {
  const config = loadDockerConfig();
  const runId = `${mission.jobType}-${Date.now()}`;
  const outputDir = path.join(config.outputRoot, runId);
  await fs.mkdir(outputDir, { recursive: true });

  const missionPath = path.join(outputDir, "mission.json");
  await fs.writeFile(missionPath, JSON.stringify(mission, null, 2));

  const args = [
    "run",
    "--rm",
    "-v",
    `${outputDir}:/output`,
    "-v",
    `${missionPath}:/input/mission.json:ro`,
  ];

  for (const [key, value] of Object.entries(config.env)) {
    args.push("-e", `${key}=${value}`);
  }

  args.push(config.image, "--input", "/input/mission.json", "--output", "/output");

  const exitCode = await new Promise<number>((resolve, reject) => {
    const proc = spawn("docker", args, { stdio: "inherit" });
    proc.on("error", reject);
    proc.on("close", (code) => resolve(code ?? 1));
  });

  return { outputDir, exitCode };
}
