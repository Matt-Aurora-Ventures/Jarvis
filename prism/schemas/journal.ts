import { z } from "zod";

export const JournalEntrySchema = z.object({
  runId: z.string(),
  timestamp: z.string(),
  regime: z.string(),
  signals: z.array(z.string()),
  thresholdsChecked: z.record(z.number()),
  costBenefit: z.object({
    expectedBenefitUsd: z.number(),
    costUsd: z.number(),
    benefitCostRatio: z.number(),
  }),
  decision: z.enum(["HOLD", "EXECUTE", "ESCALATE"]),
  confidence: z.number(),
  triggers: z.array(z.string()),
  narrative: z.string(),
});

export type JournalEntry = z.infer<typeof JournalEntrySchema>;
