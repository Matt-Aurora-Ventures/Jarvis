import { buildFinanceMission, runFinanceResearchJob } from "../services/researcher/src/index.js";

async function main() {
  const mission = await buildFinanceMission(
    "volatility regimes, risk parity sizing, drawdown control in crypto"
  );
  const artifacts = await runFinanceResearchJob(mission);
  console.log(`Artifacts written to ${artifacts.outputDir}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
