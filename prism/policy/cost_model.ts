export interface CostModel {
  feeBps: number;
  slippageBps: number;
  fixedUsd: number;
}

export interface CostEstimate {
  costUsd: number;
  feeUsd: number;
  slippageUsd: number;
  fixedUsd: number;
}

export function estimateCost(model: CostModel, notionalUsd: number): CostEstimate {
  const feeUsd = (model.feeBps / 10_000) * notionalUsd;
  const slippageUsd = (model.slippageBps / 10_000) * notionalUsd;
  const costUsd = feeUsd + slippageUsd + model.fixedUsd;
  return { costUsd, feeUsd, slippageUsd, fixedUsd: model.fixedUsd };
}
