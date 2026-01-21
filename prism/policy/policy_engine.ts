import { CostModel, estimateCost } from "./cost_model.js";
import { checkMateriality, MaterialityCheck } from "./materiality.js";

export interface DecisionInputs {
  proposedNotionalUsd: number;
  expectedBenefitUsd: number;
  materialityThresholdUsd: number;
  costModel: CostModel;
  regime: string;
  allowedRegimes: string[];
}

export interface DecisionOutput {
  action: "HOLD" | "EXECUTE" | "ESCALATE";
  reasons: string[];
  materiality: MaterialityCheck;
  costEstimate: ReturnType<typeof estimateCost>;
  benefitCostRatio: number;
}

export class PolicyEngine {
  decide(inputs: DecisionInputs): DecisionOutput {
    const reasons: string[] = [];
    const materiality = checkMateriality(inputs.materialityThresholdUsd, inputs.proposedNotionalUsd);
    const costEstimate = estimateCost(inputs.costModel, inputs.proposedNotionalUsd);
    const benefitCostRatio = inputs.expectedBenefitUsd / Math.max(costEstimate.costUsd, 1e-6);

    if (!inputs.allowedRegimes.includes(inputs.regime)) {
      reasons.push(`Regime ${inputs.regime} not allowed`);
    }
    if (!materiality.passes) {
      reasons.push("Below materiality threshold");
    }
    if (inputs.expectedBenefitUsd <= 0) {
      reasons.push("No expected benefit");
    }
    if (costEstimate.costUsd >= inputs.expectedBenefitUsd) {
      reasons.push("Transaction cost exceeds expected benefit");
    }

    if (reasons.length > 0) {
      return {
        action: "HOLD",
        reasons,
        materiality,
        costEstimate,
        benefitCostRatio,
      };
    }

    return {
      action: "EXECUTE",
      reasons: ["Meets materiality and cost/benefit thresholds"],
      materiality,
      costEstimate,
      benefitCostRatio,
    };
  }
}
