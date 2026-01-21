import { z } from "zod";

export const ChangeProposalSchema = z.object({
  title: z.string(),
  motivation: z.string(),
  proposedChange: z.string(),
  status: z.literal("PROPOSED"),
  evidence: z.array(z.string()),
  evaluationPlanId: z.string().optional(),
  rollbackPlan: z.string(),
  risks: z.array(z.string()),
});

export type ChangeProposal = z.infer<typeof ChangeProposalSchema>;
