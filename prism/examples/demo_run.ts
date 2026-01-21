import { InMemoryArtifactRegistry } from "../artifacts/registry.js";
import { InMemoryDecisionLedger } from "../core/ledger.js";
import { Workflow, WorkflowEngine } from "../core/workflow.js";
import { JournalWriter } from "../agents/journal_writer.js";
import { Auditor } from "../agents/auditor.js";
import { PolicyEngine } from "../policy/policy_engine.js";
import { RiskOfficer } from "../agents/risk_officer.js";

const policyEngine = new PolicyEngine();
const riskOfficer = new RiskOfficer();
const journalWriter = new JournalWriter();
const auditor = new Auditor();
const registry = new InMemoryArtifactRegistry();
const ledger = new InMemoryDecisionLedger();

const framework = registry.create("framework", {
  materialityThresholdUsd: 500,
  allowedRegimes: ["risk-on"],
  costModel: { feeBps: 10, slippageBps: 5, fixedUsd: 1 },
});

const workflow = new Workflow("prism_demo", [
  {
    id: "policy_check_low",
    run: ({ state }) => {
      const decision = policyEngine.decide({
        proposedNotionalUsd: 100,
        expectedBenefitUsd: 10,
        materialityThresholdUsd: 500,
        costModel: { feeBps: 10, slippageBps: 5, fixedUsd: 1 },
        regime: "risk-on",
        allowedRegimes: ["risk-on"],
      });
      state.lowDecision = decision;
      return { status: "completed", output: decision };
    },
  },
  {
    id: "risk_review_low",
    run: ({ state }) => {
      const decision = state.lowDecision as { reasons: string[] };
      const risk = riskOfficer.review(decision.reasons);
      state.lowRisk = risk;
      return { status: "completed", output: risk };
    },
  },
  {
    id: "journal_low",
    run: ({ state }) => {
      const decision = state.lowDecision as {
        action: "HOLD" | "EXECUTE" | "ESCALATE";
        reasons: string[];
        materiality: { threshold: number; value: number };
        costEstimate: { costUsd: number };
        benefitCostRatio: number;
      };
      const entry = journalWriter.write({
        runId: "demo-low",
        regime: "risk-on",
        signals: ["materiality"],
        thresholdsChecked: { materiality: decision.materiality.threshold },
        costBenefit: {
          expectedBenefitUsd: 10,
          costUsd: decision.costEstimate.costUsd,
          benefitCostRatio: decision.benefitCostRatio,
        },
        decision: decision.action,
        confidence: 7,
        triggers: ["materiality"],
        narrative: "Below materiality threshold, HOLD.",
      });
      ledger.recordJournal(entry);
      return { status: "completed", output: entry };
    },
  },
  {
    id: "policy_check_high",
    run: ({ state }) => {
      const decision = policyEngine.decide({
        proposedNotionalUsd: 1000,
        expectedBenefitUsd: 250,
        materialityThresholdUsd: 500,
        costModel: { feeBps: 10, slippageBps: 5, fixedUsd: 1 },
        regime: "risk-on",
        allowedRegimes: ["risk-on"],
      });
      state.highDecision = decision;
      return { status: "completed", output: decision };
    },
  },
  {
    id: "risk_review_high",
    run: ({ state }) => {
      const decision = state.highDecision as { reasons: string[] };
      const risk = riskOfficer.review(decision.reasons);
      state.highRisk = risk;
      return { status: "completed", output: risk };
    },
  },
  {
    id: "audit",
    run: () => {
      const audit = auditor.audit("demo-run");
      ledger.recordAudit(audit);
      return { status: "completed", output: audit };
    },
  },
]);

async function main() {
  const engine = new WorkflowEngine();
  const result = await engine.start(workflow, { frameworkId: framework.id });
  console.log(result.status);
  console.log(ledger.listJournals());
  console.log(ledger.listAudits());
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
