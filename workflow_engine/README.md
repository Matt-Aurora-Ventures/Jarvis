# Jarvis Durable Workflow Engine (Foundation)

This module provides the **durable workflow core** for Jarvis. It implements
deterministic, replayable workflows with persisted step inputs/outputs and
explicit agent/tool interfaces.

## Key Concepts

- **Workflow**: Ordered deterministic steps.
- **Execution Context**: Immutable input, mutable state, versioned outputs.
- **Persistence Layer**: Abstract store for workflow metadata, step runs, errors.
- **Agent Roles**: Planner, Executor, Verifier, Reducer interfaces.
- **Tool Interface**: Structured tool invocations with logs.

## Folder Structure

```
workflow_engine/
  README.md
  package.json
  tsconfig.json
  src/
    agents.ts
    engine.ts
    example.ts
    persistence.ts
    tools.ts
    types.ts
    workflow.ts
```

## Example: Goal → Plan → Execute → Verify

```ts
import { InMemoryPersistence } from "./persistence";
import { WorkflowEngine } from "./engine";
import { StepDefinition, StepStatus } from "./types";
import { Workflow } from "./workflow";

const steps: StepDefinition[] = [
  {
    id: "plan",
    execute: ({ input, state }) => {
      state.plan = [`Do thing for ${input.goal}`];
      return { status: StepStatus.Completed, output: state.plan };
    },
  },
  {
    id: "execute",
    execute: ({ state }) => {
      state.result = `Executed: ${state.plan[0]}`;
      return { status: StepStatus.Completed, output: state.result };
    },
  },
  {
    id: "verify",
    execute: ({ state }) => {
      const ok = state.result.includes("Executed");
      return {
        status: ok ? StepStatus.Completed : StepStatus.Failed,
        output: { ok },
        error: ok ? undefined : "Verification failed",
      };
    },
  },
];

const workflow = new Workflow("goal_to_verify", steps);
const engine = new WorkflowEngine(new InMemoryPersistence());

const run = await engine.start(workflow, { goal: "build foundation" });
console.log(run.status); // completed
```

## Pause / Resume / Replay

- **Pause**: A step can return `StepStatus.Paused`, preserving state.
- **Resume**: `engine.resume(workflowId)` continues from the next pending step.
- **Replay**: `engine.replay(workflowId)` replays from stored step outputs.

## Notes

- No chatbot UI or provider-specific LLM integration.
- No global mutable state.
- Deterministic, inspectable execution by design.
