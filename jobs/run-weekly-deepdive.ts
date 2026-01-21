import { buildAIMLMission, runWeeklyDeepDiveJob } from "../services/researcher/src/index.js";

async function main() {
  const mission = await buildAIMLMission(
    "agent workflow reliability, evaluation harnesses, durable execution patterns",
    "weekly"
  );
  const artifacts = await runWeeklyDeepDiveJob(mission);
  console.log(`Artifacts written to ${artifacts.outputDir}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
