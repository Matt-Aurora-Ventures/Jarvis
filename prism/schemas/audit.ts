import { z } from "zod";

export const AuditRecordSchema = z.object({
  runId: z.string(),
  timestamp: z.string(),
  complianceScore: z.number(),
  violations: z.array(z.string()),
  rootCauseAnalysis: z.array(z.string()),
  recommendedProcessChanges: z.array(z.string()),
  experimentsToRunNext: z.array(z.string()),
});

export type AuditRecord = z.infer<typeof AuditRecordSchema>;
