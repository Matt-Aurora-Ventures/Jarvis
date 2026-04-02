/**
 * Time-Based Reward Math
 * Prompt #34: Precise time-weighted staking calculations with fixed-point math
 */

use anchor_lang::prelude::*;

// =============================================================================
// CONSTANTS
// =============================================================================

/// Precision for fixed-point math (1e9)
pub const PRECISION: u128 = 1_000_000_000;

/// Seconds per day
pub const SECONDS_PER_DAY: i64 = 86_400;

/// Multiplier tiers (scaled by 100)
pub const MULTIPLIER_BRONZE: u64 = 100;   // 1.0x (days 0-6)
pub const MULTIPLIER_SILVER: u64 = 150;   // 1.5x (days 7-29)
pub const MULTIPLIER_GOLD: u64 = 200;     // 2.0x (days 30-89)
pub const MULTIPLIER_DIAMOND: u64 = 250;  // 2.5x (days 90+)

/// Tier boundaries in days
pub const TIER_BRONZE_END: i64 = 6;
pub const TIER_SILVER_END: i64 = 29;
pub const TIER_GOLD_END: i64 = 89;

// =============================================================================
// REWARD CALCULATION
// =============================================================================

/// Input parameters for reward calculation
#[derive(Debug, Clone)]
pub struct RewardCalculationInput {
    pub user_stake_amount: u64,
    pub stake_start_time: i64,
    pub last_claim_time: i64,
    pub current_time: i64,
    pub global_reward_rate: u64,  // Rewards per second per staked token (scaled by PRECISION)
    pub early_holder_bonus: u64,   // Additional multiplier (scaled by 100)
}

/// Output of reward calculation
#[derive(Debug, Clone)]
pub struct RewardCalculationOutput {
    pub total_pending_rewards: u64,
    pub rewards_per_tier: TierRewards,
    pub effective_multiplier: u64,
    pub time_in_each_tier: TierDurations,
}

/// Rewards broken down by tier
#[derive(Debug, Clone, Default)]
pub struct TierRewards {
    pub bronze_rewards: u64,
    pub silver_rewards: u64,
    pub gold_rewards: u64,
    pub diamond_rewards: u64,
}

/// Time spent in each tier during reward period
#[derive(Debug, Clone, Default)]
pub struct TierDurations {
    pub bronze_seconds: i64,
    pub silver_seconds: i64,
    pub gold_seconds: i64,
    pub diamond_seconds: i64,
}

/// Calculate rewards with time-weighted multipliers
pub fn calculate_rewards(input: &RewardCalculationInput) -> Result<RewardCalculationOutput> {
    // Validate inputs
    require!(input.current_time >= input.last_claim_time, RewardError::InvalidTimeRange);
    require!(input.stake_start_time <= input.last_claim_time, RewardError::InvalidTimeRange);

    if input.user_stake_amount == 0 {
        return Ok(RewardCalculationOutput {
            total_pending_rewards: 0,
            rewards_per_tier: TierRewards::default(),
            effective_multiplier: MULTIPLIER_BRONZE,
            time_in_each_tier: TierDurations::default(),
        });
    }

    // Calculate time spent in each tier during the reward period
    let tier_durations = calculate_tier_durations(
        input.stake_start_time,
        input.last_claim_time,
        input.current_time,
    );

    // Calculate rewards for each tier
    let tier_rewards = calculate_tier_rewards(
        input.user_stake_amount,
        input.global_reward_rate,
        &tier_durations,
        input.early_holder_bonus,
    )?;

    // Sum total rewards
    let total = tier_rewards.bronze_rewards
        .checked_add(tier_rewards.silver_rewards)
        .ok_or(RewardError::Overflow)?
        .checked_add(tier_rewards.gold_rewards)
        .ok_or(RewardError::Overflow)?
        .checked_add(tier_rewards.diamond_rewards)
        .ok_or(RewardError::Overflow)?;

    // Calculate current effective multiplier
    let days_staked = (input.current_time - input.stake_start_time) / SECONDS_PER_DAY;
    let effective_multiplier = get_multiplier_for_days(days_staked)
        .max(input.early_holder_bonus);

    Ok(RewardCalculationOutput {
        total_pending_rewards: total,
        rewards_per_tier: tier_rewards,
        effective_multiplier,
        time_in_each_tier: tier_durations,
    })
}

/// Calculate how much time was spent in each tier during the reward period
fn calculate_tier_durations(
    stake_start_time: i64,
    last_claim_time: i64,
    current_time: i64,
) -> TierDurations {
    let mut durations = TierDurations::default();

    // Convert tier boundaries to absolute timestamps
    let bronze_end = stake_start_time + (TIER_BRONZE_END + 1) * SECONDS_PER_DAY;
    let silver_end = stake_start_time + (TIER_SILVER_END + 1) * SECONDS_PER_DAY;
    let gold_end = stake_start_time + (TIER_GOLD_END + 1) * SECONDS_PER_DAY;

    // Calculate time in Bronze tier (days 0-6)
    if last_claim_time < bronze_end {
        let start = last_claim_time;
        let end = current_time.min(bronze_end);
        if end > start {
            durations.bronze_seconds = end - start;
        }
    }

    // Calculate time in Silver tier (days 7-29)
    if current_time > bronze_end && last_claim_time < silver_end {
        let start = last_claim_time.max(bronze_end);
        let end = current_time.min(silver_end);
        if end > start {
            durations.silver_seconds = end - start;
        }
    }

    // Calculate time in Gold tier (days 30-89)
    if current_time > silver_end && last_claim_time < gold_end {
        let start = last_claim_time.max(silver_end);
        let end = current_time.min(gold_end);
        if end > start {
            durations.gold_seconds = end - start;
        }
    }

    // Calculate time in Diamond tier (days 90+)
    if current_time > gold_end {
        let start = last_claim_time.max(gold_end);
        let end = current_time;
        if end > start {
            durations.diamond_seconds = end - start;
        }
    }

    durations
}

/// Calculate rewards for each tier
fn calculate_tier_rewards(
    stake_amount: u64,
    reward_rate: u64,
    durations: &TierDurations,
    early_bonus: u64,
) -> Result<TierRewards> {
    let mut rewards = TierRewards::default();

    // For each tier: rewards = stake * rate * time * multiplier / PRECISION / 100
    // Using max(tier_multiplier, early_bonus)

    if durations.bronze_seconds > 0 {
        let multiplier = MULTIPLIER_BRONZE.max(early_bonus);
        rewards.bronze_rewards = calculate_tier_reward(
            stake_amount,
            reward_rate,
            durations.bronze_seconds,
            multiplier,
        )?;
    }

    if durations.silver_seconds > 0 {
        let multiplier = MULTIPLIER_SILVER.max(early_bonus);
        rewards.silver_rewards = calculate_tier_reward(
            stake_amount,
            reward_rate,
            durations.silver_seconds,
            multiplier,
        )?;
    }

    if durations.gold_seconds > 0 {
        let multiplier = MULTIPLIER_GOLD.max(early_bonus);
        rewards.gold_rewards = calculate_tier_reward(
            stake_amount,
            reward_rate,
            durations.gold_seconds,
            multiplier,
        )?;
    }

    if durations.diamond_seconds > 0 {
        let multiplier = MULTIPLIER_DIAMOND.max(early_bonus);
        rewards.diamond_rewards = calculate_tier_reward(
            stake_amount,
            reward_rate,
            durations.diamond_seconds,
            multiplier,
        )?;
    }

    Ok(rewards)
}

/// Calculate reward for a single tier
fn calculate_tier_reward(
    stake_amount: u64,
    reward_rate: u64,
    seconds: i64,
    multiplier: u64,
) -> Result<u64> {
    // reward = stake * rate * seconds * multiplier / PRECISION / 100
    // Using u128 to prevent overflow

    let stake = stake_amount as u128;
    let rate = reward_rate as u128;
    let time = seconds as u128;
    let mult = multiplier as u128;

    let numerator = stake
        .checked_mul(rate)
        .ok_or(RewardError::Overflow)?
        .checked_mul(time)
        .ok_or(RewardError::Overflow)?
        .checked_mul(mult)
        .ok_or(RewardError::Overflow)?;

    let denominator = PRECISION * 100;

    let result = numerator / denominator;

    // Convert back to u64, saturating at max
    Ok(result.min(u64::MAX as u128) as u64)
}

/// Get multiplier for number of days staked
pub fn get_multiplier_for_days(days: i64) -> u64 {
    match days {
        0..=6 => MULTIPLIER_BRONZE,
        7..=29 => MULTIPLIER_SILVER,
        30..=89 => MULTIPLIER_GOLD,
        _ => MULTIPLIER_DIAMOND,
    }
}

// =============================================================================
// PARTIAL UNSTAKE CALCULATION
// =============================================================================

/// Calculate rewards for partial unstake
pub fn calculate_partial_unstake_rewards(
    input: &RewardCalculationInput,
    unstake_percentage: u64,  // Percentage to unstake (0-100)
) -> Result<(u64, u64)> {  // Returns (rewards_to_claim, remaining_stake)
    require!(unstake_percentage <= 100, RewardError::InvalidPercentage);

    // First, calculate total pending rewards
    let full_rewards = calculate_rewards(input)?;

    // Calculate proportional rewards
    let rewards_to_claim = (full_rewards.total_pending_rewards as u128
        * unstake_percentage as u128 / 100) as u64;

    // Calculate remaining stake
    let unstake_amount = (input.user_stake_amount as u128
        * unstake_percentage as u128 / 100) as u64;
    let remaining_stake = input.user_stake_amount.saturating_sub(unstake_amount);

    Ok((rewards_to_claim, remaining_stake))
}

// =============================================================================
// REWARD RATE CHANGE HANDLING
// =============================================================================

/// Snapshot rewards before rate change
pub fn snapshot_rewards_before_rate_change(
    input: &RewardCalculationInput,
) -> Result<u64> {
    // Calculate rewards up to current time with old rate
    let output = calculate_rewards(input)?;
    Ok(output.total_pending_rewards)
}

/// Calculate accrued rewards with rate change mid-period
pub fn calculate_with_rate_change(
    stake_amount: u64,
    stake_start_time: i64,
    last_claim_time: i64,
    rate_change_time: i64,
    old_rate: u64,
    new_rate: u64,
    current_time: i64,
    early_bonus: u64,
) -> Result<u64> {
    // Period 1: last_claim_time to rate_change_time with old_rate
    let period1_input = RewardCalculationInput {
        user_stake_amount: stake_amount,
        stake_start_time,
        last_claim_time,
        current_time: rate_change_time,
        global_reward_rate: old_rate,
        early_holder_bonus: early_bonus,
    };
    let period1_rewards = calculate_rewards(&period1_input)?.total_pending_rewards;

    // Period 2: rate_change_time to current_time with new_rate
    let period2_input = RewardCalculationInput {
        user_stake_amount: stake_amount,
        stake_start_time,
        last_claim_time: rate_change_time,
        current_time,
        global_reward_rate: new_rate,
        early_holder_bonus: early_bonus,
    };
    let period2_rewards = calculate_rewards(&period2_input)?.total_pending_rewards;

    Ok(period1_rewards.checked_add(period2_rewards).ok_or(RewardError::Overflow)?)
}

// =============================================================================
// APY CALCULATION
// =============================================================================

/// Calculate current APY based on reward rate and TVL
pub fn calculate_apy(
    reward_rate: u64,      // Rewards per second per token (scaled by PRECISION)
    total_staked: u64,     // Total tokens staked
    token_price_usd: u64,  // Token price in cents
    sol_price_usd: u64,    // SOL price in cents
) -> u64 {
    if total_staked == 0 || token_price_usd == 0 {
        return 0;
    }

    // Annual rewards per token = rate * seconds_per_year / PRECISION
    let seconds_per_year: u128 = 365 * 24 * 60 * 60;
    let annual_rewards_per_token = (reward_rate as u128 * seconds_per_year) / PRECISION;

    // Convert to USD value: (annual_sol_rewards * sol_price) / token_price
    let annual_usd_value = (annual_rewards_per_token * sol_price_usd as u128) / 1_000_000_000; // lamports to SOL

    // APY = (annual_usd_value / token_price) * 10000 (basis points)
    let apy_bps = (annual_usd_value * 10000) / token_price_usd as u128;

    apy_bps.min(u64::MAX as u128) as u64
}

// =============================================================================
// ERROR CODES
// =============================================================================

#[error_code]
pub enum RewardError {
    #[msg("Arithmetic overflow in reward calculation")]
    Overflow,

    #[msg("Invalid time range for calculation")]
    InvalidTimeRange,

    #[msg("Invalid percentage value")]
    InvalidPercentage,

    #[msg("Division by zero")]
    DivisionByZero,
}

// =============================================================================
// TESTS
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_reward_calculation() {
        let input = RewardCalculationInput {
            user_stake_amount: 1_000_000_000, // 1 token with 9 decimals
            stake_start_time: 0,
            last_claim_time: 0,
            current_time: 86400, // 1 day
            global_reward_rate: 1_000_000, // 1e-3 SOL per second per token
            early_holder_bonus: 100, // No bonus
        };

        let result = calculate_rewards(&input).unwrap();
        assert!(result.total_pending_rewards > 0);
        assert!(result.time_in_each_tier.bronze_seconds == 86400);
    }

    #[test]
    fn test_tier_transitions() {
        let input = RewardCalculationInput {
            user_stake_amount: 1_000_000_000,
            stake_start_time: 0,
            last_claim_time: 0,
            current_time: 30 * 86400, // 30 days
            global_reward_rate: 1_000_000,
            early_holder_bonus: 100,
        };

        let result = calculate_rewards(&input).unwrap();
        assert!(result.time_in_each_tier.bronze_seconds > 0);
        assert!(result.time_in_each_tier.silver_seconds > 0);
        assert!(result.time_in_each_tier.gold_seconds > 0);
    }

    #[test]
    fn test_early_holder_bonus() {
        let input_no_bonus = RewardCalculationInput {
            user_stake_amount: 1_000_000_000,
            stake_start_time: 0,
            last_claim_time: 0,
            current_time: 86400,
            global_reward_rate: 1_000_000,
            early_holder_bonus: 100, // 1.0x
        };

        let input_with_bonus = RewardCalculationInput {
            early_holder_bonus: 300, // 3.0x Diamond bonus
            ..input_no_bonus.clone()
        };

        let result_no_bonus = calculate_rewards(&input_no_bonus).unwrap();
        let result_with_bonus = calculate_rewards(&input_with_bonus).unwrap();

        assert!(result_with_bonus.total_pending_rewards > result_no_bonus.total_pending_rewards);
    }

    #[test]
    fn test_multiplier_for_days() {
        assert_eq!(get_multiplier_for_days(0), MULTIPLIER_BRONZE);
        assert_eq!(get_multiplier_for_days(6), MULTIPLIER_BRONZE);
        assert_eq!(get_multiplier_for_days(7), MULTIPLIER_SILVER);
        assert_eq!(get_multiplier_for_days(29), MULTIPLIER_SILVER);
        assert_eq!(get_multiplier_for_days(30), MULTIPLIER_GOLD);
        assert_eq!(get_multiplier_for_days(89), MULTIPLIER_GOLD);
        assert_eq!(get_multiplier_for_days(90), MULTIPLIER_DIAMOND);
        assert_eq!(get_multiplier_for_days(365), MULTIPLIER_DIAMOND);
    }
}
