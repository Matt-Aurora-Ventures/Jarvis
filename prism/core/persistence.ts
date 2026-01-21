import { RunStatus, StepStatus } from "./state.js";

export interface WorkflowRecord {
  workflowId: string;
  name: string;
  status: RunStatus;
  inputSnapshot: unknown;
  createdAt: string;
  updatedAt: string;
}

export interface StepRecord {
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

export interface PersistenceLayer {
  createWorkflow(record: WorkflowRecord): Promise<void>;
  updateWorkflowStatus(workflowId: string, status: RunStatus): Promise<void>;
  getWorkflow(workflowId: string): Promise<WorkflowRecord | undefined>;
  listWorkflows(): Promise<WorkflowRecord[]>;
  appendStep(record: StepRecord): Promise<void>;
  listSteps(workflowId: string): Promise<StepRecord[]>;
}

export class InMemoryPersistence implements PersistenceLayer {
  private workflows = new Map<string, WorkflowRecord>();
  private steps = new Map<string, StepRecord[]>();

  async createWorkflow(record: WorkflowRecord): Promise<void> {
    this.workflows.set(record.workflowId, record);
    this.steps.set(record.workflowId, []);
  }

  async updateWorkflowStatus(workflowId: string, status: RunStatus): Promise<void> {
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

  async appendStep(record: StepRecord): Promise<void> {
    const records = this.steps.get(record.workflowId) ?? [];
    records.push(record);
    this.steps.set(record.workflowId, records);
  }

  async listSteps(workflowId: string): Promise<StepRecord[]> {
    return this.steps.get(workflowId) ?? [];
  }
}
