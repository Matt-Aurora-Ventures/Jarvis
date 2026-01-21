export type ResearchJobType = "finance" | "aiml";

export interface ResearchMission {
  jobType: ResearchJobType;
  scope: "daily" | "weekly";
  topic: string;
  requester: string;
  prompt: string;
}

export interface ResearchArtifacts {
  runId: string;
  outputDir: string;
  reportPath: string;
  claimsPath: string;
  changeProposalPath?: string;
  evaluationPlanPath?: string;
  runMetaPath: string;
}
