import { z } from "zod";

export const FrameworkSpecSchema = z.object({
  frameworkId: z.string(),
  version: z.string(),
  assetUniverse: z.array(z.string()),
  actionUniverse: z.array(z.string()),
  requiredInputs: z.array(z.string()),
  derivedSignals: z.array(z.string()),
  regimeClassifier: z.array(z.string()),
  positionLimits: z.record(z.string()),
  triggers: z.array(z.string()),
  costModel: z.object({
    feeBps: z.number(),
    slippageBps: z.number(),
    fixedUsd: z.number(),
  }),
  decisionPolicy: z.string(),
  journalingSchema: z.string(),
  safetyConstraints: z.array(z.string()),
});

export type FrameworkSpec = z.infer<typeof FrameworkSpecSchema>;
