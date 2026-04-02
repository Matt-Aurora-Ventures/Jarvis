import {
  ExecutionContext,
  StepDefinition,
  StepRunRecord,
  StepStatus,
  WorkflowRecord,
  WorkflowStatus,
} from "./types.js";
import { PersistenceLayer } from "./persistence.js";
import { Workflow } from "./workflow.js";

export interface WorkflowRunResult {
  workflowId: string;
  status: WorkflowStatus;
  context: ExecutionContext;
}

export class WorkflowEngine {
  constructor(private persistence: PersistenceLayer) {}

  async start<Input, State>(
    workflow: Workflow<Input, State>,
    input: Input,
    initialState?: State
  ): Promise<WorkflowRunResult> {
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
  ): Promise<WorkflowRunResult> {
    return this.run(workflow, workflowId, input, initialState);
  }

  async replay<Input, State>(
    workflow: Workflow<Input, State>,
    workflowId: string,
    input: Input,
    initialState?: State
  ): Promise<WorkflowRunResult> {
    const runs = await this.persistence.listStepRuns(workflowId);
    const context = workflow.createContext(input, initialState);
    for (const run of runs) {
      if (run.outputSnapshot !== undefined) {
        context.outputs[run.stepId] = context.outputs[run.stepId] ?? [];
        context.outputs[run.stepId].push(run.outputSnapshot);
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
  ): Promise<WorkflowRunResult> {
    const context = workflow.createContext(input, initialState);
    const runs = await this.persistence.listStepRuns(workflowId);
    const completedStepIds = new Set(
      runs.filter((run) => run.status === StepStatus.Completed).map((run) => run.stepId)
    );

    for (const step of workflow.steps) {
      if (completedStepIds.has(step.id)) {
        continue;
      }

      const startedAt = new Date().toISOString();
      const result = workflow.executeStep(step, context);
      const finishedAt = new Date().toISOString();

      const record: StepRunRecord = {
        workflowId,
        stepId: step.id,
        status: result.status,
        inputSnapshot: { input: context.input, state: context.state },
        outputSnapshot: result.output,
        error: result.error,
        startedAt,
        finishedAt,
        attempt: runs.filter((run) => run.stepId === step.id).length + 1,
      };
      await this.persistence.appendStepRun(record);

      if (result.output !== undefined) {
        context.outputs[step.id] = context.outputs[step.id] ?? [];
        context.outputs[step.id].push(result.output);
      }

      if (result.status === StepStatus.Paused) {
        await this.persistence.updateWorkflowStatus(workflowId, "paused");
        return { workflowId, status: "paused", context };
      }

      if (result.status === StepStatus.Failed) {
        await this.persistence.updateWorkflowStatus(workflowId, "failed");
        return { workflowId, status: "failed", context };
      }
    }

    await this.persistence.updateWorkflowStatus(workflowId, "completed");
    return { workflowId, status: "completed", context };
  }
}
