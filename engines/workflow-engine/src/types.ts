export enum StepStatus {
  Pending = "pending",
  Running = "running",
  Completed = "completed",
  Failed = "failed",
  Paused = "paused",
}

export type WorkflowStatus = "pending" | "running" | "completed" | "failed" | "paused";

export interface StepExecutionResult<Output = unknown> {
  status: StepStatus;
  output?: Output;
  error?: string;
}

export interface ExecutionContext<Input = unknown, State = Record<string, unknown>> {
  readonly input: Input;
  state: State;
  outputs: Record<string, unknown[]>;
}

export interface StepDefinition<Input = unknown, State = Record<string, unknown>, Output = unknown> {
  id: string;
  execute: (context: ExecutionContext<Input, State>) => StepExecutionResult<Output>;
}

export interface StepRunRecord {
  workflowId: string;
  stepId: string;
  status: StepStatus;
  inputSnapshot: unknown;
  outputSnapshot?: unknown;
  error?: string;
  startedAt: string;
  finishedAt?: string;
  attempt: number;
}

export interface WorkflowRecord {
  workflowId: string;
  name: string;
  status: WorkflowStatus;
  inputSnapshot: unknown;
  createdAt: string;
  updatedAt: string;
}
