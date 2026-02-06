/**
 * Token Maturity Scoring - Bags.fm Integration
 * 
 * Weights pre-migration tokens based on:
 * - Bonding Curve Progress (25%)
 * - Market Depth/Liquidity (25%)
 * - Creator Metrics (20%)
 * - Social Signals (15%)
 * - Distribution Health (15%)
 */

export interface TokenMetrics {
    mint: string;
    symbol: string;
    name: string;

    // Bonding curve metrics
    bondingCurveProgress: number; // 0-100%
    currentMarketCap: number;
    graduationThreshold: number;

    // Market metrics
    liquidity: number;
    volume24h: number;
    priceChange24h: number;
    holdersCount: number;

    // Creator metrics
    creatorFeePercent: number;
    creatorSolBalance: number;
    creatorTokenBalance: number;
    isCreatorVerified: boolean;

    // Social metrics
    twitterFollowers?: number;
    telegramMembers?: number;
    discordMembers?: number;

    // Distribution
    top10HoldersPercent: number;
    devHoldingsPercent: number;
}

export interface MaturityScore {
    total: number; // 0-100

    // Component scores
    bondingCurve: number;
    market: number;
    creator: number;
    social: number;
    distribution: number;

    // Risk assessment
    tier: 'exceptional' | 'strong' | 'average' | 'weak' | 'poor';
    isGraduationReady: boolean;
    warnings: string[];

    // Weights used
    weights: typeof DEFAULT_WEIGHTS;
}

// Default weights (can be dynamically calibrated)
export const DEFAULT_WEIGHTS = {
    bondingCurve: 0.25,
    market: 0.25,
    creator: 0.20,
    social: 0.15,
    distribution: 0.15,
};

// Thresholds for scoring tiers
const TIER_THRESHOLDS = {
    exceptional: 80,
    strong: 65,
    average: 50,
    weak: 35,
};

/**
 * Calculate maturity score for a token
 */
export function calculateMaturityScore(
    metrics: TokenMetrics,
    weights = DEFAULT_WEIGHTS
): MaturityScore {
    const warnings: string[] = [];

    // 1. Bonding Curve Score (0-100)
    // Higher progress = closer to graduation = higher score
    const bondingCurveScore = Math.min(100, metrics.bondingCurveProgress);

    // Warning if stuck near graduation
    if (bondingCurveScore > 90 && bondingCurveScore < 100) {
        warnings.push('Token near graduation threshold but not crossed');
    }

    // 2. Market Score (0-100)
    // Based on liquidity depth and volume health
    const liquidityScore = Math.min(100, (metrics.liquidity / 50000) * 100); // $50k = 100
    const volumeScore = Math.min(100, (metrics.volume24h / 25000) * 100); // $25k/day = 100
    const holdersScore = Math.min(100, (metrics.holdersCount / 500) * 100); // 500 holders = 100

    const marketScore = (liquidityScore * 0.5) + (volumeScore * 0.3) + (holdersScore * 0.2);

    if (metrics.liquidity < 5000) {
        warnings.push('Very low liquidity - high slippage risk');
    }

    // 3. Creator Score (0-100)
    // Penalize high fees, reward verified & balanced holdings
    let creatorScore = 50; // Base score

    // Fee penalty (ideal: 1-2%)
    if (metrics.creatorFeePercent <= 2) {
        creatorScore += 20;
    } else if (metrics.creatorFeePercent >= 5) {
        creatorScore -= 20;
        warnings.push(`High creator fee: ${metrics.creatorFeePercent}%`);
    }

    // Verification bonus
    if (metrics.isCreatorVerified) {
        creatorScore += 15;
    }

    // SOL balance (shows commitment)
    if (metrics.creatorSolBalance >= 1) {
        creatorScore += 15;
    }

    creatorScore = Math.max(0, Math.min(100, creatorScore));

    // 4. Social Score (0-100)
    // Aggregate social presence
    const twitter = Math.min(40, ((metrics.twitterFollowers || 0) / 5000) * 40);
    const telegram = Math.min(30, ((metrics.telegramMembers || 0) / 2000) * 30);
    const discord = Math.min(30, ((metrics.discordMembers || 0) / 1000) * 30);

    const socialScore = twitter + telegram + discord;

    if (socialScore < 20) {
        warnings.push('Limited social presence');
    }

    // 5. Distribution Score (0-100)
    // Penalize concentrated holdings
    let distributionScore = 100;

    // Top 10 holders concentration penalty
    if (metrics.top10HoldersPercent > 50) {
        distributionScore -= (metrics.top10HoldersPercent - 50);
        warnings.push(`Top 10 wallets hold ${metrics.top10HoldersPercent.toFixed(1)}%`);
    }

    // Dev holdings penalty
    if (metrics.devHoldingsPercent > 10) {
        distributionScore -= (metrics.devHoldingsPercent - 10) * 2;
        warnings.push(`Dev holds ${metrics.devHoldingsPercent.toFixed(1)}% of supply`);
    }

    distributionScore = Math.max(0, distributionScore);

    // Calculate weighted total
    const total =
        bondingCurveScore * weights.bondingCurve +
        marketScore * weights.market +
        creatorScore * weights.creator +
        socialScore * weights.social +
        distributionScore * weights.distribution;

    // Determine tier
    let tier: MaturityScore['tier'];
    if (total >= TIER_THRESHOLDS.exceptional) {
        tier = 'exceptional';
    } else if (total >= TIER_THRESHOLDS.strong) {
        tier = 'strong';
    } else if (total >= TIER_THRESHOLDS.average) {
        tier = 'average';
    } else if (total >= TIER_THRESHOLDS.weak) {
        tier = 'weak';
    } else {
        tier = 'poor';
    }

    return {
        total: Math.round(total),
        bondingCurve: Math.round(bondingCurveScore),
        market: Math.round(marketScore),
        creator: Math.round(creatorScore),
        social: Math.round(socialScore),
        distribution: Math.round(distributionScore),
        tier,
        isGraduationReady: bondingCurveScore >= 100,
        warnings,
        weights,
    };
}

/**
 * Get position size multiplier based on maturity score
 */
export function getPositionSizeMultiplier(score: MaturityScore): number {
    switch (score.tier) {
        case 'exceptional': return 1.0;   // Full size
        case 'strong': return 0.75;       // 75%
        case 'average': return 0.5;       // 50%
        case 'weak': return 0.25;         // 25%
        case 'poor': return 0;            // Don't trade
    }
}

/**
 * Check if token should be auto-exited based on score degradation
 */
export function shouldAutoExit(
    currentScore: MaturityScore,
    entryScore: number,
    degradationThreshold = 20
): { shouldExit: boolean; reason?: string } {
    const scoreDrop = entryScore - currentScore.total;

    if (scoreDrop >= degradationThreshold) {
        return {
            shouldExit: true,
            reason: `Score dropped ${scoreDrop} points (${entryScore} → ${currentScore.total})`,
        };
    }

    if (currentScore.tier === 'poor') {
        return {
            shouldExit: true,
            reason: 'Token degraded to POOR tier',
        };
    }

    // Critical warning check
    const criticalWarnings = currentScore.warnings.filter(w =>
        w.includes('Very low liquidity') ||
        w.includes('High creator fee') ||
        w.includes('Top 10 wallets hold')
    );

    if (criticalWarnings.length >= 2) {
        return {
            shouldExit: true,
            reason: `Multiple critical warnings: ${criticalWarnings.join(', ')}`,
        };
    }

    return { shouldExit: false };
}
