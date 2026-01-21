import { StepRunRecord, WorkflowRecord, WorkflowStatus } from "./types.js";

export interface PersistenceLayer {
  createWorkflow(record: WorkflowRecord): Promise<void>;
  updateWorkflowStatus(workflowId: string, status: WorkflowStatus): Promise<void>;
  getWorkflow(workflowId: string): Promise<WorkflowRecord | undefined>;
  listWorkflows(): Promise<WorkflowRecord[]>;
  appendStepRun(record: StepRunRecord): Promise<void>;
  listStepRuns(workflowId: string): Promise<StepRunRecord[]>;
}

export class InMemoryPersistence implements PersistenceLayer {
  private workflows = new Map<string, WorkflowRecord>();
  private stepRuns = new Map<string, StepRunRecord[]>();

  async createWorkflow(record: WorkflowRecord): Promise<void> {
    this.workflows.set(record.workflowId, record);
    this.stepRuns.set(record.workflowId, []);
  }

  async updateWorkflowStatus(workflowId: string, status: WorkflowStatus): Promise<void> {
    const record = this.workflows.get(workflowId);
    if (!record) {
      return;
    }
    record.status = status;
    record.updatedAt = new Date().toISOString();
    this.workflows.set(workflowId, record);
  }

  async getWorkflow(workflowId: string): Promise<WorkflowRecord | undefined> {
    return this.workflows.get(workflowId);
  }

  async listWorkflows(): Promise<WorkflowRecord[]> {
    return Array.from(this.workflows.values());
  }

  async appendStepRun(record: StepRunRecord): Promise<void> {
    const runs = this.stepRuns.get(record.workflowId) ?? [];
    runs.push(record);
    this.stepRuns.set(record.workflowId, runs);
  }

  async listStepRuns(workflowId: string): Promise<StepRunRecord[]> {
    return this.stepRuns.get(workflowId) ?? [];
  }
}
