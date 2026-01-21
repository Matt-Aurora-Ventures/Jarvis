export type RunStatus = "pending" | "running" | "completed" | "failed" | "paused";

export interface RunState<Input = unknown, State = Record<string, unknown>> {
  readonly input: Input;
  state: State;
  outputs: Record<string, unknown[]>;
}

export interface WorkflowStep<Input = unknown, State = Record<string, unknown>, Output = unknown> {
  id: string;
  run: (context: RunState<Input, State>) => StepResult<Output>;
}

export type StepStatus = "pending" | "running" | "completed" | "failed" | "paused";

export interface StepResult<Output = unknown> {
  status: StepStatus;
  output?: Output;
  error?: string;
}
