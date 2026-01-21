import { buildAIMLMission, buildFinanceMission, runAIMLScanJob, runFinanceResearchJob } from "./index.js";

const args = process.argv.slice(2);

async function main() {
  const jobType = args[0];
  const topicIndex = args.indexOf("--topic");
  const topic = topicIndex >= 0 ? args[topicIndex + 1] : "";
  if (!jobType || !topic) {
    throw new Error("Usage: node cli.ts <finance|aiml> --topic <topic>");
  }

  if (jobType === "finance") {
    const mission = await buildFinanceMission(topic);
    await runFinanceResearchJob(mission);
    return;
  }

  if (jobType === "aiml") {
    const mission = await buildAIMLMission(topic, "daily");
    await runAIMLScanJob(mission);
    return;
  }

  throw new Error("Unknown job type");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
