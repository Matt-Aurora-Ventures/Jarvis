import { InMemoryPersistence, PersistenceLayer, StepRecord, WorkflowRecord } from "./persistence.js";
import { RunState, StepResult, StepStatus, WorkflowStep, RunStatus } from "./state.js";

export interface WorkflowRunResult<Input = unknown, State = Record<string, unknown>> {
  workflowId: string;
  status: RunStatus;
  context: RunState<Input, State>;
}

export class Workflow<Input = unknown, State = Record<string, unknown>> {
  constructor(public readonly name: string, public readonly steps: WorkflowStep<Input, State, unknown>[]) {}

  createContext(input: Input, initialState?: State): RunState<Input, State> {
    return {
      input,
      state: initialState ?? ({} as State),
      outputs: {},
    };
  }
}

export class WorkflowEngine {
  constructor(private persistence: PersistenceLayer = new InMemoryPersistence()) {}

  async start<Input, State>(
    workflow: Workflow<Input, State>,
    input: Input,
    initialState?: State
  ): Promise<WorkflowRunResult<Input, State>> {
    const workflowId = `${workflow.name}-${Date.now()}`;
    const record: WorkflowRecord = {
      workflowId,
      name: workflow.name,
      status: "running",
      inputSnapshot: input,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    await this.persistence.createWorkflow(record);
    return this.run(workflow, workflowId, input, initialState);
  }

  async resume<Input, State>(
    workflow: Workflow<Input, State>,
    workflowId: string,
    input: Input,
    initialState?: State
  ): Promise<WorkflowRunResult<Input, State>> {
    return this.run(workflow, workflowId, input, initialState);
  }

  async replay<Input, State>(
    workflow: Workflow<Input, State>,
    workflowId: string,
    input: Input,
    initialState?: State
  ): Promise<WorkflowRunResult<Input, State>> {
    const context = workflow.createContext(input, initialState);
    const steps = await this.persistence.listSteps(workflowId);
    for (const record of steps) {
      if (record.outputSnapshot !== undefined) {
        context.outputs[record.stepId] = context.outputs[record.stepId] ?? [];
        context.outputs[record.stepId].push(record.outputSnapshot);
      }
    }
    const status = (await this.persistence.getWorkflow(workflowId))?.status ?? "pending";
    return { workflowId, status, context };
  }

  private async run<Input, State>(
    workflow: Workflow<Input, State>,
    workflowId: string,
    input: Input,
    initialState?: State
  ): Promise<WorkflowRunResult<Input, State>> {
    const context = workflow.createContext(input, initialState);
    const stepHistory = await this.persistence.listSteps(workflowId);
    const completed = new Set(stepHistory.filter((s) => s.status === "completed").map((s) => s.stepId));

    for (const step of workflow.steps) {
      if (completed.has(step.id)) {
        continue;
      }
      const startedAt = new Date().toISOString();
      const result: StepResult = step.run(context);
      const finishedAt = new Date().toISOString();

      const record: StepRecord = {
        workflowId,
        stepId: step.id,
        status: result.status,
        inputSnapshot: { input: context.input, state: context.state },
        outputSnapshot: result.output,
        error: result.error,
        startedAt,
        finishedAt,
        attempt: stepHistory.filter((s) => s.stepId === step.id).length + 1,
      };

      await this.persistence.appendStep(record);
      if (result.output !== undefined) {
        context.outputs[step.id] = context.outputs[step.id] ?? [];
        context.outputs[step.id].push(result.output);
      }

      if (result.status === "paused") {
        await this.persistence.updateWorkflowStatus(workflowId, "paused");
        return { workflowId, status: "paused", context };
      }
      if (result.status === "failed") {
        await this.persistence.updateWorkflowStatus(workflowId, "failed");
        return { workflowId, status: "failed", context };
      }
    }

    await this.persistence.updateWorkflowStatus(workflowId, "completed");
    return { workflowId, status: "completed", context };
  }
}
