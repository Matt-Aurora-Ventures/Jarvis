export interface PlannerAgent<Goal = unknown> {
  plan(goal: Goal): Promise<{ steps: string[]; rationale?: string }>;
}

export interface ExecutorAgent {
  execute(step: string): Promise<{ output: unknown; status: "completed" | "failed" }>;
}

export interface VerifierAgent<Output = unknown> {
  verify(output: Output): Promise<{ ok: boolean; reason?: string }>;
}

export interface ReducerAgent<Payload = unknown> {
  reduce(payload: Payload): Promise<{ summary: string; facts: string[]; risks: string[]; questions: string[] }>;
}
