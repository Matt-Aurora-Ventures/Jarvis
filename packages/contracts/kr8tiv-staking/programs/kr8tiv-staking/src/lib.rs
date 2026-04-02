use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer, Mint};

declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

/// KR8TIV Staking Program
///
/// Features:
/// - Stake $KR8TIV tokens to earn SOL rewards
/// - Time-weighted reward multipliers (up to 2.5x)
/// - Claim rewards without unstaking
/// - 3-day cooldown for unstaking
/// - Admin controls for reward deposits and emergency actions
///
/// Multiplier Schedule:
/// - 1-7 days: 1.0x
/// - 7-30 days: 1.5x
/// - 30-90 days: 2.0x
/// - 90+ days: 2.5x

#[program]
pub mod kr8tiv_staking {
    use super::*;

    /// Initialize the staking pool
    pub fn initialize_pool(
        ctx: Context<InitializePool>,
        reward_rate: u64,  // Rewards per token per second (scaled by 1e9)
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;

        pool.authority = ctx.accounts.authority.key();
        pool.staking_mint = ctx.accounts.staking_mint.key();
        pool.staking_vault = ctx.accounts.staking_vault.key();
        pool.reward_vault = ctx.accounts.reward_vault.key();
        pool.reward_rate = reward_rate;
        pool.total_staked = 0;
        pool.reward_per_token_stored = 0;
        pool.last_update_time = Clock::get()?.unix_timestamp as u64;
        pool.paused = false;
        pool.bump = ctx.bumps.pool;

        msg!("Pool initialized with reward rate: {}", reward_rate);
        Ok(())
    }

    /// Stake tokens into the pool
    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        require!(amount > 0, StakingError::InvalidAmount);
        require!(!ctx.accounts.pool.paused, StakingError::PoolPaused);

        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;
        let clock = Clock::get()?;
        let now = clock.unix_timestamp as u64;

        // Update pool rewards
        update_rewards(pool, now)?;

        // Update user rewards before changing stake
        if user_stake.amount > 0 {
            let pending = calculate_pending_rewards(pool, user_stake, now)?;
            user_stake.pending_rewards = user_stake.pending_rewards
                .checked_add(pending)
                .ok_or(StakingError::MathOverflow)?;
        } else {
            // First stake - record start time
            user_stake.stake_start_time = now;
        }

        // Transfer tokens to vault
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_token_account.to_account_info(),
                    to: ctx.accounts.staking_vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            amount,
        )?;

        // Update state
        user_stake.amount = user_stake.amount
            .checked_add(amount)
            .ok_or(StakingError::MathOverflow)?;
        user_stake.reward_per_token_paid = pool.reward_per_token_stored;
        user_stake.last_stake_time = now;

        pool.total_staked = pool.total_staked
            .checked_add(amount)
            .ok_or(StakingError::MathOverflow)?;

        emit!(StakeEvent {
            user: ctx.accounts.user.key(),
            amount,
            total_staked: user_stake.amount,
            timestamp: now,
        });

        msg!("Staked {} tokens", amount);
        Ok(())
    }

    /// Initiate unstake (starts cooldown)
    pub fn initiate_unstake(ctx: Context<InitiateUnstake>, amount: u64) -> Result<()> {
        require!(amount > 0, StakingError::InvalidAmount);

        let user_stake = &mut ctx.accounts.user_stake;
        require!(amount <= user_stake.amount, StakingError::InsufficientStake);
        require!(user_stake.cooldown_end == 0, StakingError::CooldownActive);

        let clock = Clock::get()?;
        let now = clock.unix_timestamp as u64;

        // Update rewards before starting cooldown
        let pool = &mut ctx.accounts.pool;
        update_rewards(pool, now)?;

        let pending = calculate_pending_rewards(pool, user_stake, now)?;
        user_stake.pending_rewards = user_stake.pending_rewards
            .checked_add(pending)
            .ok_or(StakingError::MathOverflow)?;
        user_stake.reward_per_token_paid = pool.reward_per_token_stored;

        // Set cooldown (3 days = 259200 seconds)
        user_stake.cooldown_amount = amount;
        user_stake.cooldown_end = now + COOLDOWN_DURATION;

        emit!(UnstakeInitiatedEvent {
            user: ctx.accounts.user.key(),
            amount,
            cooldown_end: user_stake.cooldown_end,
        });

        msg!("Unstake initiated for {} tokens, cooldown ends at {}",
             amount, user_stake.cooldown_end);
        Ok(())
    }

    /// Complete unstake after cooldown
    pub fn complete_unstake(ctx: Context<CompleteUnstake>) -> Result<()> {
        let user_stake = &mut ctx.accounts.user_stake;
        let pool = &mut ctx.accounts.pool;

        require!(user_stake.cooldown_amount > 0, StakingError::NoCooldownActive);

        let clock = Clock::get()?;
        let now = clock.unix_timestamp as u64;

        require!(now >= user_stake.cooldown_end, StakingError::CooldownNotComplete);

        let amount = user_stake.cooldown_amount;

        // Update rewards
        update_rewards(pool, now)?;
        let pending = calculate_pending_rewards(pool, user_stake, now)?;
        user_stake.pending_rewards = user_stake.pending_rewards
            .checked_add(pending)
            .ok_or(StakingError::MathOverflow)?;

        // Transfer tokens back to user
        let seeds = &[
            b"pool".as_ref(),
            &[pool.bump],
        ];
        let signer = &[&seeds[..]];

        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.staking_vault.to_account_info(),
                    to: ctx.accounts.user_token_account.to_account_info(),
                    authority: pool.to_account_info(),
                },
                signer,
            ),
            amount,
        )?;

        // Update state
        user_stake.amount = user_stake.amount
            .checked_sub(amount)
            .ok_or(StakingError::MathOverflow)?;
        user_stake.cooldown_amount = 0;
        user_stake.cooldown_end = 0;
        user_stake.reward_per_token_paid = pool.reward_per_token_stored;

        // Reset stake start time if fully unstaked
        if user_stake.amount == 0 {
            user_stake.stake_start_time = 0;
        }

        pool.total_staked = pool.total_staked
            .checked_sub(amount)
            .ok_or(StakingError::MathOverflow)?;

        emit!(UnstakeCompletedEvent {
            user: ctx.accounts.user.key(),
            amount,
            remaining_stake: user_stake.amount,
            timestamp: now,
        });

        msg!("Unstake completed for {} tokens", amount);
        Ok(())
    }

    /// Claim pending rewards (SOL)
    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;

        let clock = Clock::get()?;
        let now = clock.unix_timestamp as u64;

        // Update rewards
        update_rewards(pool, now)?;

        let pending = calculate_pending_rewards(pool, user_stake, now)?;
        let total_rewards = user_stake.pending_rewards
            .checked_add(pending)
            .ok_or(StakingError::MathOverflow)?;

        require!(total_rewards > 0, StakingError::NoRewardsToClaim);

        // Apply time-weighted multiplier
        let multiplier = get_time_multiplier(user_stake.stake_start_time, now);
        let final_rewards = (total_rewards as u128)
            .checked_mul(multiplier as u128)
            .ok_or(StakingError::MathOverflow)?
            .checked_div(MULTIPLIER_PRECISION as u128)
            .ok_or(StakingError::MathOverflow)? as u64;

        // Check reward vault has enough
        require!(
            ctx.accounts.reward_vault.lamports() >= final_rewards,
            StakingError::InsufficientRewardBalance
        );

        // Transfer SOL rewards
        **ctx.accounts.reward_vault.try_borrow_mut_lamports()? -= final_rewards;
        **ctx.accounts.user.try_borrow_mut_lamports()? += final_rewards;

        // Update state
        user_stake.pending_rewards = 0;
        user_stake.reward_per_token_paid = pool.reward_per_token_stored;
        user_stake.total_rewards_claimed = user_stake.total_rewards_claimed
            .checked_add(final_rewards)
            .ok_or(StakingError::MathOverflow)?;

        emit!(RewardsClaimedEvent {
            user: ctx.accounts.user.key(),
            amount: final_rewards,
            multiplier,
            timestamp: now,
        });

        msg!("Claimed {} lamports in rewards ({}x multiplier)",
             final_rewards, multiplier as f64 / MULTIPLIER_PRECISION as f64);
        Ok(())
    }

    /// Admin: Deposit SOL rewards to pool
    pub fn deposit_rewards(ctx: Context<DepositRewards>, amount: u64) -> Result<()> {
        require!(amount > 0, StakingError::InvalidAmount);

        // Transfer SOL to reward vault
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.authority.key(),
            &ctx.accounts.reward_vault.key(),
            amount,
        );

        anchor_lang::solana_program::program::invoke(
            &ix,
            &[
                ctx.accounts.authority.to_account_info(),
                ctx.accounts.reward_vault.to_account_info(),
            ],
        )?;

        emit!(RewardsDepositedEvent {
            authority: ctx.accounts.authority.key(),
            amount,
            timestamp: Clock::get()?.unix_timestamp as u64,
        });

        msg!("Deposited {} lamports to reward vault", amount);
        Ok(())
    }

    /// Admin: Update reward rate
    pub fn update_reward_rate(ctx: Context<AdminAction>, new_rate: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let now = Clock::get()?.unix_timestamp as u64;

        // Update stored rewards before changing rate
        update_rewards(pool, now)?;

        let old_rate = pool.reward_rate;
        pool.reward_rate = new_rate;

        emit!(RewardRateUpdatedEvent {
            old_rate,
            new_rate,
            timestamp: now,
        });

        msg!("Reward rate updated from {} to {}", old_rate, new_rate);
        Ok(())
    }

    /// Admin: Pause/unpause staking
    pub fn set_paused(ctx: Context<AdminAction>, paused: bool) -> Result<()> {
        ctx.accounts.pool.paused = paused;

        msg!("Pool paused: {}", paused);
        Ok(())
    }

    /// Admin: Emergency withdraw all tokens (use with caution!)
    pub fn emergency_withdraw(ctx: Context<EmergencyWithdraw>) -> Result<()> {
        let pool = &ctx.accounts.pool;
        let amount = ctx.accounts.staking_vault.amount;

        require!(amount > 0, StakingError::NoTokensToWithdraw);

        let seeds = &[
            b"pool".as_ref(),
            &[pool.bump],
        ];
        let signer = &[&seeds[..]];

        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.staking_vault.to_account_info(),
                    to: ctx.accounts.destination.to_account_info(),
                    authority: ctx.accounts.pool.to_account_info(),
                },
                signer,
            ),
            amount,
        )?;

        emit!(EmergencyWithdrawEvent {
            authority: ctx.accounts.authority.key(),
            amount,
            timestamp: Clock::get()?.unix_timestamp as u64,
        });

        msg!("Emergency withdraw: {} tokens", amount);
        Ok(())
    }
}

// =============================================================================
// Constants
// =============================================================================

/// Cooldown duration in seconds (3 days)
pub const COOLDOWN_DURATION: u64 = 3 * 24 * 60 * 60;

/// Multiplier precision (1e6)
pub const MULTIPLIER_PRECISION: u64 = 1_000_000;

/// Time thresholds for multipliers
pub const TIER_1_THRESHOLD: u64 = 7 * 24 * 60 * 60;    // 7 days
pub const TIER_2_THRESHOLD: u64 = 30 * 24 * 60 * 60;   // 30 days
pub const TIER_3_THRESHOLD: u64 = 90 * 24 * 60 * 60;   // 90 days

/// Multiplier values (scaled by MULTIPLIER_PRECISION)
pub const MULTIPLIER_BASE: u64 = 1_000_000;     // 1.0x
pub const MULTIPLIER_TIER_1: u64 = 1_500_000;   // 1.5x
pub const MULTIPLIER_TIER_2: u64 = 2_000_000;   // 2.0x
pub const MULTIPLIER_TIER_3: u64 = 2_500_000;   // 2.5x

// =============================================================================
// Helper Functions
// =============================================================================

/// Update global reward accounting
fn update_rewards(pool: &mut Account<StakingPool>, now: u64) -> Result<()> {
    if pool.total_staked > 0 {
        let time_elapsed = now.saturating_sub(pool.last_update_time);
        let new_rewards = (pool.reward_rate as u128)
            .checked_mul(time_elapsed as u128)
            .ok_or(StakingError::MathOverflow)?;

        let reward_per_token_increase = new_rewards
            .checked_mul(1_000_000_000)  // Scale for precision
            .ok_or(StakingError::MathOverflow)?
            .checked_div(pool.total_staked as u128)
            .ok_or(StakingError::MathOverflow)?;

        pool.reward_per_token_stored = pool.reward_per_token_stored
            .checked_add(reward_per_token_increase as u64)
            .ok_or(StakingError::MathOverflow)?;
    }

    pool.last_update_time = now;
    Ok(())
}

/// Calculate pending rewards for a user (before multiplier)
fn calculate_pending_rewards(
    pool: &Account<StakingPool>,
    user_stake: &Account<UserStake>,
    _now: u64,
) -> Result<u64> {
    if user_stake.amount == 0 {
        return Ok(0);
    }

    let reward_per_token_diff = pool.reward_per_token_stored
        .saturating_sub(user_stake.reward_per_token_paid);

    let pending = (user_stake.amount as u128)
        .checked_mul(reward_per_token_diff as u128)
        .ok_or(StakingError::MathOverflow)?
        .checked_div(1_000_000_000)  // Unscale
        .ok_or(StakingError::MathOverflow)? as u64;

    Ok(pending)
}

/// Get time-weighted multiplier based on stake duration
fn get_time_multiplier(stake_start: u64, now: u64) -> u64 {
    if stake_start == 0 {
        return MULTIPLIER_BASE;
    }

    let duration = now.saturating_sub(stake_start);

    if duration >= TIER_3_THRESHOLD {
        MULTIPLIER_TIER_3
    } else if duration >= TIER_2_THRESHOLD {
        MULTIPLIER_TIER_2
    } else if duration >= TIER_1_THRESHOLD {
        MULTIPLIER_TIER_1
    } else {
        MULTIPLIER_BASE
    }
}

// =============================================================================
// Accounts
// =============================================================================

#[derive(Accounts)]
pub struct InitializePool<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + StakingPool::LEN,
        seeds = [b"pool"],
        bump
    )]
    pub pool: Account<'info, StakingPool>,

    pub staking_mint: Account<'info, Mint>,

    #[account(
        init,
        payer = authority,
        token::mint = staking_mint,
        token::authority = pool,
        seeds = [b"staking_vault"],
        bump
    )]
    pub staking_vault: Account<'info, TokenAccount>,

    /// CHECK: This is a SOL vault, validated by seed
    #[account(
        mut,
        seeds = [b"reward_vault"],
        bump
    )]
    pub reward_vault: AccountInfo<'info>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct Stake<'info> {
    #[account(
        mut,
        seeds = [b"pool"],
        bump = pool.bump
    )]
    pub pool: Account<'info, StakingPool>,

    #[account(
        init_if_needed,
        payer = user,
        space = 8 + UserStake::LEN,
        seeds = [b"user_stake", user.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,

    #[account(
        mut,
        constraint = staking_vault.key() == pool.staking_vault
    )]
    pub staking_vault: Account<'info, TokenAccount>,

    #[account(
        mut,
        constraint = user_token_account.mint == pool.staking_mint,
        constraint = user_token_account.owner == user.key()
    )]
    pub user_token_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub user: Signer<'info>,

    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct InitiateUnstake<'info> {
    #[account(
        mut,
        seeds = [b"pool"],
        bump = pool.bump
    )]
    pub pool: Account<'info, StakingPool>,

    #[account(
        mut,
        seeds = [b"user_stake", user.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,

    pub user: Signer<'info>,
}

#[derive(Accounts)]
pub struct CompleteUnstake<'info> {
    #[account(
        mut,
        seeds = [b"pool"],
        bump = pool.bump
    )]
    pub pool: Account<'info, StakingPool>,

    #[account(
        mut,
        seeds = [b"user_stake", user.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,

    #[account(
        mut,
        constraint = staking_vault.key() == pool.staking_vault
    )]
    pub staking_vault: Account<'info, TokenAccount>,

    #[account(
        mut,
        constraint = user_token_account.mint == pool.staking_mint,
        constraint = user_token_account.owner == user.key()
    )]
    pub user_token_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub user: Signer<'info>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct ClaimRewards<'info> {
    #[account(
        mut,
        seeds = [b"pool"],
        bump = pool.bump
    )]
    pub pool: Account<'info, StakingPool>,

    #[account(
        mut,
        seeds = [b"user_stake", user.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,

    /// CHECK: SOL reward vault
    #[account(
        mut,
        seeds = [b"reward_vault"],
        bump
    )]
    pub reward_vault: AccountInfo<'info>,

    #[account(mut)]
    pub user: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct DepositRewards<'info> {
    #[account(
        seeds = [b"pool"],
        bump = pool.bump,
        has_one = authority
    )]
    pub pool: Account<'info, StakingPool>,

    /// CHECK: SOL reward vault
    #[account(
        mut,
        seeds = [b"reward_vault"],
        bump
    )]
    pub reward_vault: AccountInfo<'info>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AdminAction<'info> {
    #[account(
        mut,
        seeds = [b"pool"],
        bump = pool.bump,
        has_one = authority
    )]
    pub pool: Account<'info, StakingPool>,

    pub authority: Signer<'info>,
}

#[derive(Accounts)]
pub struct EmergencyWithdraw<'info> {
    #[account(
        seeds = [b"pool"],
        bump = pool.bump,
        has_one = authority
    )]
    pub pool: Account<'info, StakingPool>,

    #[account(
        mut,
        constraint = staking_vault.key() == pool.staking_vault
    )]
    pub staking_vault: Account<'info, TokenAccount>,

    #[account(mut)]
    pub destination: Account<'info, TokenAccount>,

    pub authority: Signer<'info>,

    pub token_program: Program<'info, Token>,
}

// =============================================================================
// State
// =============================================================================

#[account]
pub struct StakingPool {
    /// Pool authority (admin)
    pub authority: Pubkey,
    /// Token mint for staking
    pub staking_mint: Pubkey,
    /// Vault holding staked tokens
    pub staking_vault: Pubkey,
    /// Vault holding SOL rewards
    pub reward_vault: Pubkey,
    /// Reward rate per token per second (scaled by 1e9)
    pub reward_rate: u64,
    /// Total tokens staked
    pub total_staked: u64,
    /// Accumulated reward per token (scaled)
    pub reward_per_token_stored: u64,
    /// Last time rewards were updated
    pub last_update_time: u64,
    /// Whether staking is paused
    pub paused: bool,
    /// PDA bump
    pub bump: u8,
}

impl StakingPool {
    pub const LEN: usize = 32 + 32 + 32 + 32 + 8 + 8 + 8 + 8 + 1 + 1;
}

#[account]
pub struct UserStake {
    /// Amount of tokens staked
    pub amount: u64,
    /// When user first staked (for multiplier calculation)
    pub stake_start_time: u64,
    /// Last time user staked more tokens
    pub last_stake_time: u64,
    /// Reward per token paid (for calculating pending rewards)
    pub reward_per_token_paid: u64,
    /// Pending rewards to be claimed
    pub pending_rewards: u64,
    /// Total rewards claimed all time
    pub total_rewards_claimed: u64,
    /// Amount in cooldown for unstaking
    pub cooldown_amount: u64,
    /// When cooldown ends (0 if not in cooldown)
    pub cooldown_end: u64,
}

impl UserStake {
    pub const LEN: usize = 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8;
}

// =============================================================================
// Events
// =============================================================================

#[event]
pub struct StakeEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub total_staked: u64,
    pub timestamp: u64,
}

#[event]
pub struct UnstakeInitiatedEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub cooldown_end: u64,
}

#[event]
pub struct UnstakeCompletedEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub remaining_stake: u64,
    pub timestamp: u64,
}

#[event]
pub struct RewardsClaimedEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub multiplier: u64,
    pub timestamp: u64,
}

#[event]
pub struct RewardsDepositedEvent {
    pub authority: Pubkey,
    pub amount: u64,
    pub timestamp: u64,
}

#[event]
pub struct RewardRateUpdatedEvent {
    pub old_rate: u64,
    pub new_rate: u64,
    pub timestamp: u64,
}

#[event]
pub struct EmergencyWithdrawEvent {
    pub authority: Pubkey,
    pub amount: u64,
    pub timestamp: u64,
}

// =============================================================================
// Errors
// =============================================================================

#[error_code]
pub enum StakingError {
    #[msg("Invalid amount")]
    InvalidAmount,

    #[msg("Pool is paused")]
    PoolPaused,

    #[msg("Insufficient stake balance")]
    InsufficientStake,

    #[msg("Cooldown already active")]
    CooldownActive,

    #[msg("No cooldown active")]
    NoCooldownActive,

    #[msg("Cooldown not complete")]
    CooldownNotComplete,

    #[msg("No rewards to claim")]
    NoRewardsToClaim,

    #[msg("Insufficient reward balance in vault")]
    InsufficientRewardBalance,

    #[msg("No tokens to withdraw")]
    NoTokensToWithdraw,

    #[msg("Math overflow")]
    MathOverflow,
}
