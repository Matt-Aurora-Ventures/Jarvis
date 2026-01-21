import { ExecutionContext, StepDefinition, StepExecutionResult, StepStatus } from "./types.js";

export class Workflow<Input = unknown, State = Record<string, unknown>> {
  public readonly name: string;
  public readonly steps: StepDefinition<Input, State, unknown>[];

  constructor(name: string, steps: StepDefinition<Input, State, unknown>[]) {
    this.name = name;
    this.steps = steps;
  }

  createContext(input: Input, initialState?: State): ExecutionContext<Input, State> {
    return {
      input,
      state: initialState ?? ({} as State),
      outputs: {},
    };
  }

  executeStep(
    step: StepDefinition<Input, State, unknown>,
    context: ExecutionContext<Input, State>
  ): StepExecutionResult {
    return step.execute(context);
  }
}
