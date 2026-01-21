export interface ToolInvocation {
  toolName: string;
  input: Record<string, unknown>;
  startedAt: string;
  finishedAt?: string;
  output?: Record<string, unknown>;
  error?: string;
}

export interface Tool {
  name: string;
  invoke(input: Record<string, unknown>): Promise<Record<string, unknown>>;
}

export class ToolRegistry {
  private tools = new Map<string, Tool>();
  private logs: ToolInvocation[] = [];

  register(tool: Tool): void {
    this.tools.set(tool.name, tool);
  }

  getLogs(): ToolInvocation[] {
    return [...this.logs];
  }

  async invoke(toolName: string, input: Record<string, unknown>): Promise<Record<string, unknown>> {
    const tool = this.tools.get(toolName);
    const startedAt = new Date().toISOString();
    const invocation: ToolInvocation = { toolName, input, startedAt };
    if (!tool) {
      invocation.error = "Tool not registered";
      invocation.finishedAt = new Date().toISOString();
      this.logs.push(invocation);
      throw new Error(`Tool not registered: ${toolName}`);
    }

    try {
      const output = await tool.invoke(input);
      invocation.output = output;
      invocation.finishedAt = new Date().toISOString();
      this.logs.push(invocation);
      return output;
    } catch (error) {
      invocation.error = error instanceof Error ? error.message : String(error);
      invocation.finishedAt = new Date().toISOString();
      this.logs.push(invocation);
      throw error;
    }
  }
}
