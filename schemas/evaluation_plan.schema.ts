import { z } from "zod";

export const EvaluationPlanSchema = z.object({
  planId: z.string(),
  datasets: z.array(z.string()),
  baselines: z.array(z.string()),
  metrics: z.array(z.string()),
  acceptanceThresholds: z.array(z.string()),
  reproducibility: z.string(),
});

export type EvaluationPlan = z.infer<typeof EvaluationPlanSchema>;
