import { promises as fs } from "node:fs";
import path from "node:path";

import { ClaimSetSchema } from "../../../schemas/claim_set.schema.js";
import { ChangeProposalSchema } from "../../../schemas/change_proposal.schema.js";
import { EvaluationPlanSchema } from "../../../schemas/evaluation_plan.schema.js";
import { ResearchReportSchema } from "../../../schemas/research_report.schema.js";
import { ArtifactRunMeta } from "../../../core/artifacts/types.js";
import { ArtifactRegistry, FilesystemArtifactRegistry } from "../../../core/artifacts/fs_registry.js";
import { buildRunId } from "../../../core/artifacts/naming.js";
import { ResearchArtifacts, ResearchMission } from "./types.js";

export interface NormalizeResult {
  artifacts: ResearchArtifacts;
  runMeta: ArtifactRunMeta;
}

async function loadJsonFile(filePath: string): Promise<unknown | null> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function normalizeOutput(
  mission: ResearchMission,
  outputDir: string,
  registry: ArtifactRegistry = new FilesystemArtifactRegistry()
): Promise<NormalizeResult> {
  const runId = buildRunId(mission.jobType);
  const runDir = await registry.createRunDir(mission.jobType, runId);

  const reportPath = path.join(outputDir, "report.md");
  const reportContent = await fs.readFile(reportPath, "utf-8").catch(() => "");
  const report = ResearchReportSchema.safeParse({
    title: `${mission.jobType.toUpperCase()} Research`,
    summary: reportContent || "No report content produced.",
    citations: [],
    nextQuestions: [],
  });

  await registry.writeReport(runDir, report.success ? report.data.summary : reportContent);

  const claimsRaw = await loadJsonFile(path.join(outputDir, "claims.json"));
  const claims = ClaimSetSchema.safeParse(claimsRaw ?? { claims: [] });
  const claimsPath = await registry.writeJson(runDir, "claims.json", claims.success ? claims.data : { claims: [] });

  const changeRaw = await loadJsonFile(path.join(outputDir, "change_proposal.json"));
  const change = ChangeProposalSchema.safeParse(changeRaw ?? null);
  const changeProposalPath = change.success
    ? await registry.writeJson(runDir, "change_proposal.json", change.data)
    : undefined;

  const evalRaw = await loadJsonFile(path.join(outputDir, "evaluation_plan.json"));
  const evaluation = EvaluationPlanSchema.safeParse(evalRaw ?? null);
  const evaluationPlanPath = evaluation.success
    ? await registry.writeJson(runDir, "evaluation_plan.json", evaluation.data)
    : undefined;

  const runMeta: ArtifactRunMeta = {
    runId,
    jobType: mission.jobType,
    createdAt: new Date().toISOString(),
    status: change.success ? "PROPOSED" : "COMPLETE",
    sources: report.success ? report.data.citations : [],
    assumptions: ["AI-Researcher output normalized by Jarvis"],
    riskNotes: [],
  };
  const runMetaPath = await registry.writeRunMeta(runDir, runMeta);

  return {
    artifacts: {
      runId,
      outputDir: runDir,
      reportPath: path.join(runDir, "report.md"),
      claimsPath,
      changeProposalPath,
      evaluationPlanPath,
      runMetaPath,
    },
    runMeta,
  };
}
