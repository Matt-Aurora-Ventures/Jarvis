import { FrameworkSpec } from "../schemas/framework.js";

export interface FrameworkBuilder {
  build(artifactId: string): Promise<FrameworkSpec>;
}

export class StubFrameworkBuilder implements FrameworkBuilder {
  async build(): Promise<FrameworkSpec> {
    return {
      frameworkId: "demo-framework",
      version: "0.1.0",
      assetUniverse: ["DEMO"],
      actionUniverse: ["BUY", "SELL", "HOLD"],
      requiredInputs: ["price", "volatility"],
      derivedSignals: ["trend"],
      regimeClassifier: ["risk-on", "risk-off"],
      positionLimits: { default: "max 2% notional" },
      triggers: ["materiality"],
      costModel: { feeBps: 10, slippageBps: 5, fixedUsd: 1 },
      decisionPolicy: "PolicyEngine v0.1",
      journalingSchema: "JournalEntrySchema",
      safetyConstraints: ["max_daily_loss_usd"],
    };
  }
}
