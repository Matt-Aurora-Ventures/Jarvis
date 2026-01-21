export interface ExecutionReceipt {
  stepId: string;
  status: "completed" | "failed";
  output: Record<string, unknown>;
}

export interface ExecutionLog {
  stepId: string;
  action: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string;
}

export class Executor {
  execute(steps: Array<{ id: string; action: string; input: Record<string, unknown> }>): {
    executionLog: ExecutionLog[];
    receipts: ExecutionReceipt[];
    updatedState: Record<string, unknown>;
    deviations: string[];
  } {
    const executionLog: ExecutionLog[] = [];
    const receipts: ExecutionReceipt[] = [];
    const updatedState: Record<string, unknown> = {};

    for (const step of steps) {
      executionLog.push({ stepId: step.id, action: step.action, input: step.input });
      receipts.push({
        stepId: step.id,
        status: "completed",
        output: { ok: true },
      });
    }

    return {
      executionLog,
      receipts,
      updatedState,
      deviations: [],
    };
  }
}
