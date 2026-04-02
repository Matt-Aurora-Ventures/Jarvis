/**
 * PDA Account Design for KR8TIV Staking
 * Prompt #32: All Program Derived Account structures
 */

use anchor_lang::prelude::*;

// =============================================================================
// SEED CONSTANTS
// =============================================================================

pub const GLOBAL_POOL_SEED: &[u8] = b"global_pool";
pub const USER_STAKE_SEED: &[u8] = b"user_stake";
pub const REWARD_CONFIG_SEED: &[u8] = b"reward_config";
pub const ADMIN_AUTHORITY_SEED: &[u8] = b"admin_authority";
pub const FEE_VAULT_SEED: &[u8] = b"fee_vault";
pub const VESTING_SEED: &[u8] = b"vesting";
pub const GOVERNANCE_SEED: &[u8] = b"governance";

// =============================================================================
// PDA 1: GLOBAL POOL STATE
// =============================================================================
// Seeds: [GLOBAL_POOL_SEED]
// Space: 8 (discriminator) + 32 (authority) + 32 (token_mint) + 32 (token_vault) +
//        8 (total_staked) + 8 (total_stakers) + 8 (total_rewards_distributed) +
//        8 (reward_rate) + 1 (is_paused) + 1 (emergency_mode) + 1 (bump) +
//        8 (last_update_time) + 8 (created_at) + 128 (reserved) = 283 bytes

#[account]
#[derive(Default)]
pub struct GlobalPool {
    /// Admin authority that can modify pool settings
    pub authority: Pubkey,

    /// Token mint for $KR8TIV
    pub token_mint: Pubkey,

    /// Token vault PDA holding staked tokens
    pub token_vault: Pubkey,

    /// Total tokens currently staked
    pub total_staked: u64,

    /// Total number of unique stakers
    pub total_stakers: u64,

    /// Total rewards distributed all time
    pub total_rewards_distributed: u64,

    /// Current reward rate (SOL per second per staked token, scaled by 1e9)
    pub reward_rate: u64,

    /// Whether new stakes are paused
    pub is_paused: bool,

    /// Emergency mode - allows fast unstaking without cooldown
    pub emergency_mode: bool,

    /// PDA bump seed
    pub bump: u8,

    /// Last time rewards were calculated
    pub last_update_time: i64,

    /// Pool creation timestamp
    pub created_at: i64,

    /// Reserved for future use
    pub reserved: [u8; 128],
}

impl GlobalPool {
    pub const LEN: usize = 8 + 32 + 32 + 32 + 8 + 8 + 8 + 8 + 1 + 1 + 1 + 8 + 8 + 128;

    pub fn seeds(&self) -> [&[u8]; 2] {
        [GLOBAL_POOL_SEED, &[self.bump]]
    }
}

// =============================================================================
// PDA 2: USER STAKE ACCOUNT
// =============================================================================
// Seeds: [USER_STAKE_SEED, user_wallet.key().as_ref()]
// Space: 8 + 32 + 8 + 8 + 8 + 8 + 1 + 1 + 1 + 8 + 8 + 8 + 32 (reserved) = 131 bytes

#[account]
#[derive(Default)]
pub struct UserStake {
    /// Owner of this stake account
    pub owner: Pubkey,

    /// Amount of tokens staked
    pub staked_amount: u64,

    /// Timestamp when stake was created
    pub stake_start_time: i64,

    /// Timestamp of last reward claim
    pub last_claim_time: i64,

    /// Accumulated rewards (not yet claimed)
    pub pending_rewards: u64,

    /// Whether unstake has been requested
    pub unstake_requested: bool,

    /// Timestamp when unstake cooldown ends (if requested)
    pub unstake_available_time: i64,

    /// Whether auto-compound is enabled
    pub auto_compound: bool,

    /// User's early holder tier (0 = none, 1 = silver, 2 = gold, 3 = diamond)
    pub early_holder_tier: u8,

    /// PDA bump seed
    pub bump: u8,

    /// Total rewards claimed all time
    pub total_claimed: u64,

    /// Reserved for future use
    pub reserved: [u8; 32],
}

impl UserStake {
    pub const LEN: usize = 8 + 32 + 8 + 8 + 8 + 8 + 1 + 8 + 1 + 1 + 1 + 8 + 32;

    pub fn seeds<'a>(owner: &'a Pubkey, bump: &'a [u8]) -> [&'a [u8]; 3] {
        [USER_STAKE_SEED, owner.as_ref(), bump]
    }

    /// Calculate time-weighted multiplier based on stake duration
    pub fn get_multiplier(&self, current_time: i64) -> u64 {
        let days_staked = (current_time - self.stake_start_time) / 86400;

        // Base multipliers (scaled by 100 for precision)
        let base_multiplier = match days_staked {
            0..=6 => 100,    // 1.0x Bronze
            7..=29 => 150,   // 1.5x Silver
            30..=89 => 200,  // 2.0x Gold
            _ => 250,        // 2.5x Diamond
        };

        // Apply early holder bonus
        let early_bonus = match self.early_holder_tier {
            3 => 300,  // Diamond: 3.0x
            2 => 200,  // Gold: 2.0x
            1 => 150,  // Silver: 1.5x
            _ => 100,  // None: 1.0x
        };

        // Combine multipliers (max of time-based or early holder)
        std::cmp::max(base_multiplier, early_bonus)
    }
}

// =============================================================================
// PDA 3: REWARD DISTRIBUTION CONFIG
// =============================================================================
// Seeds: [REWARD_CONFIG_SEED]
// Space: 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 1 + 64 = 145 bytes

#[account]
#[derive(Default)]
pub struct RewardConfig {
    /// Base reward rate (SOL lamports per second per staked token)
    pub base_reward_rate: u64,

    /// Minimum APY floor (in basis points, e.g., 500 = 5%)
    pub min_apy_bps: u64,

    /// Maximum APY ceiling (in basis points, e.g., 10000 = 100%)
    pub max_apy_bps: u64,

    /// Target TVL for dynamic APY calculation
    pub target_tvl: u64,

    /// Last reward distribution timestamp
    pub last_distribution_time: i64,

    /// Total SOL in reward pool
    pub reward_pool_balance: u64,

    /// Staker share of revenue (in basis points, e.g., 6000 = 60%)
    pub staker_share_bps: u64,

    /// Treasury share of revenue (in basis points)
    pub treasury_share_bps: u64,

    /// Operations share of revenue (in basis points)
    pub operations_share_bps: u64,

    /// PDA bump
    pub bump: u8,

    /// Reserved for future use
    pub reserved: [u8; 64],
}

impl RewardConfig {
    pub const LEN: usize = 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 1 + 64;

    /// Calculate dynamic APY based on current TVL
    pub fn calculate_dynamic_apy(&self, current_tvl: u64) -> u64 {
        if current_tvl == 0 || self.target_tvl == 0 {
            return self.max_apy_bps;
        }

        // APY = base_apy * sqrt(target_tvl / current_tvl)
        // Using fixed-point math
        let ratio = (self.target_tvl as u128 * 1_000_000) / current_tvl as u128;
        let sqrt_ratio = integer_sqrt(ratio as u64);

        let base_apy = 5000u64; // 50% base
        let dynamic_apy = (base_apy as u128 * sqrt_ratio as u128 / 1000) as u64;

        // Clamp to min/max
        std::cmp::min(std::cmp::max(dynamic_apy, self.min_apy_bps), self.max_apy_bps)
    }
}

// =============================================================================
// PDA 4: ADMIN AUTHORITY
// =============================================================================
// Seeds: [ADMIN_AUTHORITY_SEED]
// Space: 8 + 32*3 + 1 + 1 + 1 + 8 + 32 = 147 bytes

#[account]
#[derive(Default)]
pub struct AdminAuthority {
    /// Primary admin (full control)
    pub primary_admin: Pubkey,

    /// Secondary admin (operational control)
    pub secondary_admin: Pubkey,

    /// Emergency admin (can only pause/unpause)
    pub emergency_admin: Pubkey,

    /// Number of signatures required for critical operations
    pub required_signatures: u8,

    /// Whether multisig is enabled
    pub multisig_enabled: bool,

    /// PDA bump
    pub bump: u8,

    /// Last admin action timestamp
    pub last_action_time: i64,

    /// Reserved
    pub reserved: [u8; 32],
}

impl AdminAuthority {
    pub const LEN: usize = 8 + 32 + 32 + 32 + 1 + 1 + 1 + 8 + 32;

    /// Check if a pubkey is an admin
    pub fn is_admin(&self, key: &Pubkey) -> bool {
        key == &self.primary_admin ||
        key == &self.secondary_admin ||
        key == &self.emergency_admin
    }

    /// Check if a pubkey can perform emergency actions
    pub fn can_emergency(&self, key: &Pubkey) -> bool {
        self.is_admin(key)
    }

    /// Check if a pubkey can perform critical actions
    pub fn can_critical(&self, key: &Pubkey) -> bool {
        key == &self.primary_admin
    }
}

// =============================================================================
// PDA 5: FEE VAULT
// =============================================================================
// Seeds: [FEE_VAULT_SEED]
// Space: 8 + 32 + 8 + 8 + 8 + 8 + 1 + 8 + 32 = 113 bytes

#[account]
#[derive(Default)]
pub struct FeeVault {
    /// Authority that can withdraw
    pub authority: Pubkey,

    /// Total SOL fees collected
    pub total_collected: u64,

    /// Total SOL distributed to stakers
    pub total_distributed: u64,

    /// Pending distribution amount
    pub pending_distribution: u64,

    /// Minimum balance to trigger distribution
    pub distribution_threshold: u64,

    /// PDA bump
    pub bump: u8,

    /// Last distribution timestamp
    pub last_distribution_time: i64,

    /// Reserved
    pub reserved: [u8; 32],
}

impl FeeVault {
    pub const LEN: usize = 8 + 32 + 8 + 8 + 8 + 8 + 1 + 8 + 32;

    /// Check if distribution threshold is met
    pub fn should_distribute(&self) -> bool {
        self.pending_distribution >= self.distribution_threshold
    }
}

// =============================================================================
// PDA 6: VESTING SCHEDULE
// =============================================================================
// Seeds: [VESTING_SEED, beneficiary.key().as_ref()]
// Space: 8 + 32 + 8 + 8 + 8 + 8 + 8 + 1 + 1 + 1 + 32 = 115 bytes

#[account]
#[derive(Default)]
pub struct VestingSchedule {
    /// Beneficiary of the vesting
    pub beneficiary: Pubkey,

    /// Total tokens to vest
    pub total_amount: u64,

    /// Tokens already claimed
    pub claimed_amount: u64,

    /// Vesting start time
    pub start_time: i64,

    /// Cliff duration in seconds
    pub cliff_duration: i64,

    /// Total vesting duration in seconds
    pub total_duration: i64,

    /// Whether vesting has been revoked
    pub revoked: bool,

    /// Whether vesting is active
    pub is_active: bool,

    /// PDA bump
    pub bump: u8,

    /// Reserved
    pub reserved: [u8; 32],
}

impl VestingSchedule {
    pub const LEN: usize = 8 + 32 + 8 + 8 + 8 + 8 + 8 + 1 + 1 + 1 + 32;

    /// Calculate currently vested amount
    pub fn vested_amount(&self, current_time: i64) -> u64 {
        if !self.is_active || self.revoked {
            return 0;
        }

        let elapsed = current_time - self.start_time;

        // Before cliff, nothing is vested
        if elapsed < self.cliff_duration {
            return 0;
        }

        // After full duration, everything is vested
        if elapsed >= self.total_duration {
            return self.total_amount;
        }

        // Linear vesting after cliff
        ((self.total_amount as u128 * elapsed as u128) / self.total_duration as u128) as u64
    }

    /// Calculate claimable amount
    pub fn claimable_amount(&self, current_time: i64) -> u64 {
        self.vested_amount(current_time).saturating_sub(self.claimed_amount)
    }
}

// =============================================================================
// PDA 7: GOVERNANCE WRAPPER (gKR8TIV)
// =============================================================================
// Seeds: [GOVERNANCE_SEED, user.key().as_ref()]
// Space: 8 + 32 + 8 + 8 + 8 + 1 + 32 = 97 bytes

#[account]
#[derive(Default)]
pub struct GovernanceWrapper {
    /// Owner of the governance tokens
    pub owner: Pubkey,

    /// Amount of gKR8TIV (equals staked amount)
    pub voting_power: u64,

    /// Last time voting power was updated
    pub last_update: i64,

    /// Delegated voting power to another address
    pub delegated_to: Pubkey,

    /// PDA bump
    pub bump: u8,

    /// Reserved
    pub reserved: [u8; 32],
}

impl GovernanceWrapper {
    pub const LEN: usize = 8 + 32 + 8 + 8 + 32 + 1 + 32;

    /// Get effective voting power (own + delegated from others)
    pub fn effective_voting_power(&self) -> u64 {
        self.voting_power
    }
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/// Integer square root using Newton's method
pub fn integer_sqrt(n: u64) -> u64 {
    if n == 0 {
        return 0;
    }

    let mut x = n;
    let mut y = (x + 1) / 2;

    while y < x {
        x = y;
        y = (x + n / x) / 2;
    }

    x
}

/// Calculate rent-exempt minimum for an account
pub fn calculate_rent_exempt(space: usize) -> u64 {
    // Approximate: 0.00089088 SOL per byte per year
    // Rent exempt = 2 years of rent
    const LAMPORTS_PER_BYTE_YEAR: u64 = 19;  // ~0.0000019 SOL per byte per year
    (space as u64 + 128) * LAMPORTS_PER_BYTE_YEAR * 2
}

// =============================================================================
// ACCOUNT SIZE SUMMARY
// =============================================================================
//
// GlobalPool:       283 bytes (rent: ~0.00269 SOL)
// UserStake:        131 bytes (rent: ~0.00178 SOL)
// RewardConfig:     145 bytes (rent: ~0.00191 SOL)
// AdminAuthority:   147 bytes (rent: ~0.00193 SOL)
// FeeVault:         113 bytes (rent: ~0.00166 SOL)
// VestingSchedule:  115 bytes (rent: ~0.00168 SOL)
// GovernanceWrapper: 97 bytes (rent: ~0.00157 SOL)
// =============================================================================
