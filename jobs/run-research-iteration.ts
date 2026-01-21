import { buildAIMLMission, buildFinanceMission, runAIMLScanJob, runFinanceResearchJob } from "../services/researcher/src/index.js";

async function main() {
  const iterations = Number.parseInt(process.env.JARVIS_RESEARCH_ITERATIONS ?? "2", 10);
  for (let i = 0; i < iterations; i += 1) {
    const finance = await buildFinanceMission(
      "volatility regimes, risk parity sizing, drawdown control in crypto"
    );
    await runFinanceResearchJob(finance);

    const aiml = await buildAIMLMission(
      "agent workflow reliability, evaluation harnesses, durable execution patterns",
      "daily"
    );
    await runAIMLScanJob(aiml);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
