export interface ResearchArtifact {
  researchQuestion: string;
  hypotheses: Array<{ id: string; hypothesis: string; expectedDirection: string; falsifier: string }>;
  dataRequirements: string[];
  baselineModel: string;
  candidateFeatures: string[];
  validationPlan: string;
  resultsSummary: string;
  auditTrail: string[];
}

export interface ResearchAgent {
  run(question: string): Promise<ResearchArtifact>;
}

export class StubResearchAgent implements ResearchAgent {
  async run(question: string): Promise<ResearchArtifact> {
    return {
      researchQuestion: question,
      hypotheses: [],
      dataRequirements: [],
      baselineModel: "sparse baseline (stub)",
      candidateFeatures: [],
      validationPlan: "out-of-sample validation (stub)",
      resultsSummary: "no results (stub)",
      auditTrail: [],
    };
  }
}
