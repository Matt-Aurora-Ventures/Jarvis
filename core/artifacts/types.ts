export type ArtifactStatus = "COMPLETE" | "INCOMPLETE" | "PROPOSED" | "NONE";

export interface ArtifactFileSet {
  reportPath: string;
  claimsPath: string;
  changeProposalPath?: string;
  evaluationPlanPath?: string;
  runMetaPath: string;
}

export interface ArtifactRunMeta {
  runId: string;
  jobType: string;
  createdAt: string;
  status: ArtifactStatus;
  sources: string[];
  assumptions: string[];
  riskNotes: string[];
}
