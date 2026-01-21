import { z } from "zod";

export const ResearchReportSchema = z.object({
  title: z.string(),
  summary: z.string(),
  citations: z.array(z.string()),
  nextQuestions: z.array(z.string()),
});

export type ResearchReport = z.infer<typeof ResearchReportSchema>;
