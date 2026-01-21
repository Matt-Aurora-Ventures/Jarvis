import { AuditRecord } from "../schemas/audit.js";

export class Auditor {
  audit(runId: string, violations: string[] = []): AuditRecord {
    const complianceScore = violations.length === 0 ? 100 : Math.max(0, 100 - violations.length * 10);
    return {
      runId,
      timestamp: new Date().toISOString(),
      complianceScore,
      violations,
      rootCauseAnalysis: violations.length ? ["Policy violation detected"] : [],
      recommendedProcessChanges: violations.length ? ["Tighten pre-trade checks"] : [],
      experimentsToRunNext: ["Calibrate materiality threshold"],
    };
  }
}
