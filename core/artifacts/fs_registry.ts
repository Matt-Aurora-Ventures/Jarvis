import { promises as fs } from "node:fs";
import path from "node:path";

import { ArtifactFileSet, ArtifactRunMeta } from "./types.js";

export interface ArtifactRegistry {
  createRunDir(jobType: string, runId: string): Promise<string>;
  writeReport(runDir: string, content: string): Promise<string>;
  writeJson(runDir: string, fileName: string, payload: unknown): Promise<string>;
  writeRunMeta(runDir: string, meta: ArtifactRunMeta): Promise<string>;
}

export class FilesystemArtifactRegistry implements ArtifactRegistry {
  constructor(private rootDir: string = path.join(process.cwd(), "artifacts")) {}

  async createRunDir(jobType: string, runId: string): Promise<string> {
    const runDir = path.join(this.rootDir, jobType, runId);
    await fs.mkdir(runDir, { recursive: true });
    return runDir;
  }

  async writeReport(runDir: string, content: string): Promise<string> {
    const reportPath = path.join(runDir, "report.md");
    await fs.writeFile(reportPath, content, "utf-8");
    return reportPath;
  }

  async writeJson(runDir: string, fileName: string, payload: unknown): Promise<string> {
    const filePath = path.join(runDir, fileName);
    await fs.writeFile(filePath, JSON.stringify(payload, null, 2), "utf-8");
    return filePath;
  }

  async writeRunMeta(runDir: string, meta: ArtifactRunMeta): Promise<string> {
    return this.writeJson(runDir, "run_meta.json", meta);
  }
}

export function buildArtifactFileSet(runDir: string): ArtifactFileSet {
  return {
    reportPath: path.join(runDir, "report.md"),
    claimsPath: path.join(runDir, "claims.json"),
    changeProposalPath: path.join(runDir, "change_proposal.json"),
    evaluationPlanPath: path.join(runDir, "evaluation_plan.json"),
    runMetaPath: path.join(runDir, "run_meta.json"),
  };
}
