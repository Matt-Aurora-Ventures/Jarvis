import { z } from "zod";

export const ClaimSchema = z.object({
  claimId: z.string(),
  claim: z.string(),
  evidence: z.string(),
  confidence: z.number().min(0).max(1),
  applicability: z.number().min(0).max(1),
});

export const ClaimSetSchema = z.object({
  claims: z.array(ClaimSchema),
});

export type ClaimSet = z.infer<typeof ClaimSetSchema>;
