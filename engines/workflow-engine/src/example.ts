import { Workflow } from "./workflow.js";
import { StepDefinition, StepStatus } from "./types.js";
import { InMemoryPersistence } from "./persistence.js";
import { WorkflowEngine } from "./engine.js";

type Input = { goal: string };
type State = { plan?: string[]; result?: string; verified?: boolean };

const steps: StepDefinition<Input, State>[] = [
  {
    id: "plan",
    execute: ({ input, state }) => {
      state.plan = [`Design steps for ${input.goal}`];
      return { status: StepStatus.Completed, output: state.plan };
    },
  },
  {
    id: "execute",
    execute: ({ state }) => {
      state.result = `Executed: ${state.plan?.[0] ?? "no plan"}`;
      return { status: StepStatus.Completed, output: state.result };
    },
  },
  {
    id: "verify",
    execute: ({ state }) => {
      const ok = (state.result ?? "").includes("Executed");
      state.verified = ok;
      return {
        status: ok ? StepStatus.Completed : StepStatus.Failed,
        output: { ok },
        error: ok ? undefined : "Verification failed",
      };
    },
  },
];

const workflow = new Workflow<Input, State>("goal_to_verify", steps);
const engine = new WorkflowEngine(new InMemoryPersistence());

async function main() {
  const run = await engine.start(workflow, { goal: "durable workflow foundation" });
  console.log(run);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
