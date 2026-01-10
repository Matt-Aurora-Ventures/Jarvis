use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("StakeXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX");

/// KR8TIV Staking Program
///
/// Features:
/// - Time-weighted multipliers (1.0x - 2.5x)
/// - SOL reward distribution
/// - 3-day unstake cooldown
/// - Admin controls for reward deposits
#[program]
pub mod staking {
    use super::*;

    /// Initialize the staking pool
    pub fn initialize(
        ctx: Context<Initialize>,
        reward_rate: u64,
        cooldown_days: u8,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;

        pool.authority = ctx.accounts.authority.key();
        pool.stake_mint = ctx.accounts.stake_mint.key();
        pool.reward_vault = ctx.accounts.reward_vault.key();
        pool.stake_vault = ctx.accounts.stake_vault.key();
        pool.reward_rate = reward_rate;
        pool.cooldown_seconds = (cooldown_days as i64) * 24 * 60 * 60;
        pool.total_staked = 0;
        pool.total_weight = 0;
        pool.last_update = Clock::get()?.unix_timestamp;
        pool.reward_per_weight = 0;
        pool.bump = ctx.bumps.pool;

        msg!("Pool initialized with rate {} and {} day cooldown", reward_rate, cooldown_days);
        Ok(())
    }

    /// Stake tokens
    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        require!(amount > 0, StakingError::InvalidAmount);

        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;
        let clock = Clock::get()?;

        // Update pool rewards
        update_pool_rewards(pool, clock.unix_timestamp)?;

        // Initialize or update user stake
        if user_stake.amount == 0 {
            user_stake.owner = ctx.accounts.user.key();
            user_stake.pool = pool.key();
            user_stake.stake_time = clock.unix_timestamp;
            user_stake.reward_debt = 0;
            user_stake.pending_rewards = 0;
            user_stake.unstake_time = 0;
            user_stake.bump = ctx.bumps.user_stake;
        } else {
            // Claim pending before adding more
            let pending = calculate_pending(pool, user_stake)?;
            user_stake.pending_rewards = user_stake.pending_rewards.checked_add(pending)
                .ok_or(StakingError::Overflow)?;
        }

        // Transfer tokens to vault
        let cpi_accounts = Transfer {
            from: ctx.accounts.user_token_account.to_account_info(),
            to: ctx.accounts.stake_vault.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts);
        token::transfer(cpi_ctx, amount)?;

        // Calculate weight with multiplier
        let multiplier = calculate_multiplier(0); // New stake starts at 1.0x
        let weight = (amount as u128)
            .checked_mul(multiplier as u128)
            .ok_or(StakingError::Overflow)?
            .checked_div(100)
            .ok_or(StakingError::Overflow)? as u64;

        // Update user stake
        user_stake.amount = user_stake.amount.checked_add(amount).ok_or(StakingError::Overflow)?;
        user_stake.weight = user_stake.weight.checked_add(weight).ok_or(StakingError::Overflow)?;
        user_stake.reward_debt = (user_stake.weight as u128)
            .checked_mul(pool.reward_per_weight)
            .ok_or(StakingError::Overflow)?
            .checked_div(1_000_000_000_000)
            .ok_or(StakingError::Overflow)? as u64;

        // Update pool totals
        pool.total_staked = pool.total_staked.checked_add(amount).ok_or(StakingError::Overflow)?;
        pool.total_weight = pool.total_weight.checked_add(weight).ok_or(StakingError::Overflow)?;

        msg!("Staked {} tokens with weight {}", amount, weight);

        emit!(StakeEvent {
            user: ctx.accounts.user.key(),
            amount,
            weight,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Request unstake (starts cooldown)
    pub fn request_unstake(ctx: Context<RequestUnstake>) -> Result<()> {
        let user_stake = &mut ctx.accounts.user_stake;
        let clock = Clock::get()?;

        require!(user_stake.amount > 0, StakingError::NoStake);
        require!(user_stake.unstake_time == 0, StakingError::AlreadyUnstaking);

        user_stake.unstake_time = clock.unix_timestamp;

        msg!("Unstake requested, cooldown ends at {}",
            user_stake.unstake_time + ctx.accounts.pool.cooldown_seconds);

        emit!(UnstakeRequestEvent {
            user: ctx.accounts.user.key(),
            amount: user_stake.amount,
            cooldown_ends: user_stake.unstake_time + ctx.accounts.pool.cooldown_seconds,
        });

        Ok(())
    }

    /// Complete unstake (after cooldown)
    pub fn unstake(ctx: Context<Unstake>) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;
        let clock = Clock::get()?;

        require!(user_stake.amount > 0, StakingError::NoStake);
        require!(user_stake.unstake_time > 0, StakingError::UnstakeNotRequested);

        let cooldown_end = user_stake.unstake_time + pool.cooldown_seconds;
        require!(clock.unix_timestamp >= cooldown_end, StakingError::CooldownNotComplete);

        // Update pool rewards first
        update_pool_rewards(pool, clock.unix_timestamp)?;

        // Calculate final pending rewards
        let pending = calculate_pending(pool, user_stake)?;
        let total_rewards = user_stake.pending_rewards.checked_add(pending)
            .ok_or(StakingError::Overflow)?;

        let amount = user_stake.amount;
        let weight = user_stake.weight;

        // Update pool totals
        pool.total_staked = pool.total_staked.saturating_sub(amount);
        pool.total_weight = pool.total_weight.saturating_sub(weight);

        // Transfer staked tokens back
        let seeds = &[
            b"pool".as_ref(),
            pool.stake_mint.as_ref(),
            &[pool.bump],
        ];
        let signer = &[&seeds[..]];

        let cpi_accounts = Transfer {
            from: ctx.accounts.stake_vault.to_account_info(),
            to: ctx.accounts.user_token_account.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            cpi_accounts,
            signer,
        );
        token::transfer(cpi_ctx, amount)?;

        // Transfer SOL rewards if any
        if total_rewards > 0 {
            **ctx.accounts.reward_vault.to_account_info().try_borrow_mut_lamports()? -= total_rewards;
            **ctx.accounts.user.to_account_info().try_borrow_mut_lamports()? += total_rewards;
        }

        // Reset user stake
        user_stake.amount = 0;
        user_stake.weight = 0;
        user_stake.stake_time = 0;
        user_stake.reward_debt = 0;
        user_stake.pending_rewards = 0;
        user_stake.unstake_time = 0;

        msg!("Unstaked {} tokens, claimed {} lamports rewards", amount, total_rewards);

        emit!(UnstakeEvent {
            user: ctx.accounts.user.key(),
            amount,
            rewards: total_rewards,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Claim rewards without unstaking
    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;
        let clock = Clock::get()?;

        require!(user_stake.amount > 0, StakingError::NoStake);

        // Update pool rewards
        update_pool_rewards(pool, clock.unix_timestamp)?;

        // Update weight based on time staked
        let days_staked = (clock.unix_timestamp - user_stake.stake_time) / (24 * 60 * 60);
        let new_multiplier = calculate_multiplier(days_staked as u64);
        let new_weight = (user_stake.amount as u128)
            .checked_mul(new_multiplier as u128)
            .ok_or(StakingError::Overflow)?
            .checked_div(100)
            .ok_or(StakingError::Overflow)? as u64;

        // Update pool weight difference
        if new_weight > user_stake.weight {
            let weight_diff = new_weight - user_stake.weight;
            pool.total_weight = pool.total_weight.checked_add(weight_diff)
                .ok_or(StakingError::Overflow)?;
            user_stake.weight = new_weight;
        }

        // Calculate pending rewards
        let pending = calculate_pending(pool, user_stake)?;
        let total_rewards = user_stake.pending_rewards.checked_add(pending)
            .ok_or(StakingError::Overflow)?;

        require!(total_rewards > 0, StakingError::NoRewards);

        // Transfer SOL rewards
        **ctx.accounts.reward_vault.to_account_info().try_borrow_mut_lamports()? -= total_rewards;
        **ctx.accounts.user.to_account_info().try_borrow_mut_lamports()? += total_rewards;

        // Update reward debt
        user_stake.reward_debt = (user_stake.weight as u128)
            .checked_mul(pool.reward_per_weight)
            .ok_or(StakingError::Overflow)?
            .checked_div(1_000_000_000_000)
            .ok_or(StakingError::Overflow)? as u64;
        user_stake.pending_rewards = 0;

        msg!("Claimed {} lamports rewards", total_rewards);

        emit!(ClaimEvent {
            user: ctx.accounts.user.key(),
            amount: total_rewards,
            multiplier: new_multiplier,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Deposit rewards (admin only)
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

        msg!("Deposited {} lamports to reward vault", amount);

        emit!(DepositEvent {
            authority: ctx.accounts.authority.key(),
            amount,
            timestamp: Clock::get()?.unix_timestamp,
        });

        Ok(())
    }

    /// Update reward rate (admin only)
    pub fn update_reward_rate(ctx: Context<UpdatePool>, new_rate: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let clock = Clock::get()?;

        // Update rewards before changing rate
        update_pool_rewards(pool, clock.unix_timestamp)?;

        let old_rate = pool.reward_rate;
        pool.reward_rate = new_rate;

        msg!("Reward rate updated from {} to {}", old_rate, new_rate);
        Ok(())
    }
}

// =============================================================================
// Helper Functions
// =============================================================================

fn update_pool_rewards(pool: &mut Account<Pool>, current_time: i64) -> Result<()> {
    if pool.total_weight == 0 {
        pool.last_update = current_time;
        return Ok(());
    }

    let time_elapsed = current_time.saturating_sub(pool.last_update) as u64;
    if time_elapsed == 0 {
        return Ok(());
    }

    // Calculate new rewards
    let rewards = (time_elapsed as u128)
        .checked_mul(pool.reward_rate as u128)
        .ok_or(StakingError::Overflow)?;

    // Update reward per weight (scaled by 10^12 for precision)
    let reward_per_weight_delta = rewards
        .checked_mul(1_000_000_000_000)
        .ok_or(StakingError::Overflow)?
        .checked_div(pool.total_weight as u128)
        .ok_or(StakingError::Overflow)?;

    pool.reward_per_weight = pool.reward_per_weight
        .checked_add(reward_per_weight_delta)
        .ok_or(StakingError::Overflow)?;
    pool.last_update = current_time;

    Ok(())
}

fn calculate_pending(pool: &Account<Pool>, user_stake: &Account<UserStake>) -> Result<u64> {
    let accumulated = (user_stake.weight as u128)
        .checked_mul(pool.reward_per_weight)
        .ok_or(StakingError::Overflow)?
        .checked_div(1_000_000_000_000)
        .ok_or(StakingError::Overflow)? as u64;

    Ok(accumulated.saturating_sub(user_stake.reward_debt))
}

/// Calculate time-weighted multiplier (returns value * 100 for precision)
/// 0-6 days:   100 (1.0x)
/// 7-29 days:  150 (1.5x)
/// 30-89 days: 200 (2.0x)
/// 90+ days:   250 (2.5x)
fn calculate_multiplier(days: u64) -> u64 {
    if days >= 90 {
        250
    } else if days >= 30 {
        200
    } else if days >= 7 {
        150
    } else {
        100
    }
}

// =============================================================================
// Accounts
// =============================================================================

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + Pool::INIT_SPACE,
        seeds = [b"pool", stake_mint.key().as_ref()],
        bump
    )]
    pub pool: Account<'info, Pool>,

    pub stake_mint: Account<'info, token::Mint>,

    #[account(
        init,
        payer = authority,
        token::mint = stake_mint,
        token::authority = pool,
        seeds = [b"stake_vault", pool.key().as_ref()],
        bump
    )]
    pub stake_vault: Account<'info, TokenAccount>,

    /// CHECK: PDA for holding SOL rewards
    #[account(
        seeds = [b"reward_vault", pool.key().as_ref()],
        bump
    )]
    pub reward_vault: AccountInfo<'info>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct Stake<'info> {
    #[account(mut)]
    pub pool: Account<'info, Pool>,

    #[account(
        init_if_needed,
        payer = user,
        space = 8 + UserStake::INIT_SPACE,
        seeds = [b"user_stake", pool.key().as_ref(), user.key().as_ref()],
        bump
    )]
    pub user_stake: Account<'info, UserStake>,

    #[account(mut)]
    pub stake_vault: Account<'info, TokenAccount>,

    #[account(
        mut,
        constraint = user_token_account.owner == user.key(),
        constraint = user_token_account.mint == pool.stake_mint
    )]
    pub user_token_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub user: Signer<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct RequestUnstake<'info> {
    pub pool: Account<'info, Pool>,

    #[account(
        mut,
        seeds = [b"user_stake", pool.key().as_ref(), user.key().as_ref()],
        bump = user_stake.bump,
        constraint = user_stake.owner == user.key()
    )]
    pub user_stake: Account<'info, UserStake>,

    pub user: Signer<'info>,
}

#[derive(Accounts)]
pub struct Unstake<'info> {
    #[account(mut)]
    pub pool: Account<'info, Pool>,

    #[account(
        mut,
        seeds = [b"user_stake", pool.key().as_ref(), user.key().as_ref()],
        bump = user_stake.bump,
        constraint = user_stake.owner == user.key()
    )]
    pub user_stake: Account<'info, UserStake>,

    #[account(mut)]
    pub stake_vault: Account<'info, TokenAccount>,

    #[account(
        mut,
        constraint = user_token_account.owner == user.key(),
        constraint = user_token_account.mint == pool.stake_mint
    )]
    pub user_token_account: Account<'info, TokenAccount>,

    /// CHECK: PDA for holding SOL rewards
    #[account(
        mut,
        seeds = [b"reward_vault", pool.key().as_ref()],
        bump
    )]
    pub reward_vault: AccountInfo<'info>,

    #[account(mut)]
    pub user: Signer<'info>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct ClaimRewards<'info> {
    #[account(mut)]
    pub pool: Account<'info, Pool>,

    #[account(
        mut,
        seeds = [b"user_stake", pool.key().as_ref(), user.key().as_ref()],
        bump = user_stake.bump,
        constraint = user_stake.owner == user.key()
    )]
    pub user_stake: Account<'info, UserStake>,

    /// CHECK: PDA for holding SOL rewards
    #[account(
        mut,
        seeds = [b"reward_vault", pool.key().as_ref()],
        bump
    )]
    pub reward_vault: AccountInfo<'info>,

    #[account(mut)]
    pub user: Signer<'info>,
}

#[derive(Accounts)]
pub struct DepositRewards<'info> {
    #[account(
        constraint = pool.authority == authority.key()
    )]
    pub pool: Account<'info, Pool>,

    /// CHECK: PDA for holding SOL rewards
    #[account(
        mut,
        seeds = [b"reward_vault", pool.key().as_ref()],
        bump
    )]
    pub reward_vault: AccountInfo<'info>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdatePool<'info> {
    #[account(
        mut,
        constraint = pool.authority == authority.key()
    )]
    pub pool: Account<'info, Pool>,

    pub authority: Signer<'info>,
}

// =============================================================================
// State
// =============================================================================

#[account]
#[derive(InitSpace)]
pub struct Pool {
    pub authority: Pubkey,
    pub stake_mint: Pubkey,
    pub reward_vault: Pubkey,
    pub stake_vault: Pubkey,
    pub reward_rate: u64,         // Lamports per second per weight
    pub cooldown_seconds: i64,
    pub total_staked: u64,
    pub total_weight: u64,
    pub last_update: i64,
    pub reward_per_weight: u128,  // Scaled by 10^12
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct UserStake {
    pub owner: Pubkey,
    pub pool: Pubkey,
    pub amount: u64,
    pub weight: u64,
    pub stake_time: i64,
    pub reward_debt: u64,
    pub pending_rewards: u64,
    pub unstake_time: i64,
    pub bump: u8,
}

// =============================================================================
// Events
// =============================================================================

#[event]
pub struct StakeEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub weight: u64,
    pub timestamp: i64,
}

#[event]
pub struct UnstakeRequestEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub cooldown_ends: i64,
}

#[event]
pub struct UnstakeEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub rewards: u64,
    pub timestamp: i64,
}

#[event]
pub struct ClaimEvent {
    pub user: Pubkey,
    pub amount: u64,
    pub multiplier: u64,
    pub timestamp: i64,
}

#[event]
pub struct DepositEvent {
    pub authority: Pubkey,
    pub amount: u64,
    pub timestamp: i64,
}

// =============================================================================
// Errors
// =============================================================================

#[error_code]
pub enum StakingError {
    #[msg("Invalid amount")]
    InvalidAmount,
    #[msg("No stake found")]
    NoStake,
    #[msg("Already unstaking")]
    AlreadyUnstaking,
    #[msg("Unstake not requested")]
    UnstakeNotRequested,
    #[msg("Cooldown not complete")]
    CooldownNotComplete,
    #[msg("No rewards to claim")]
    NoRewards,
    #[msg("Arithmetic overflow")]
    Overflow,
}
