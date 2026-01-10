/**
 * Emergency Shutdown System
 * Prompt #35: Emergency controls for the staking contract
 */

use anchor_lang::prelude::*;
use crate::state::{GlobalPool, AdminAuthority, UserStake, FeeVault};

// =============================================================================
// EMERGENCY STATES
// =============================================================================

/// Emergency mode levels
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, Debug)]
pub enum EmergencyLevel {
    /// Normal operation
    None = 0,

    /// Pause new stakes only (existing stakes continue earning)
    PauseNewStakes = 1,

    /// Pause all operations except emergency unstake
    PauseAll = 2,

    /// Emergency mode - instant unstake, no rewards
    EmergencyUnstake = 3,

    /// Full shutdown - admin controlled fund recovery
    FullShutdown = 4,
}

impl Default for EmergencyLevel {
    fn default() -> Self {
        EmergencyLevel::None
    }
}

// =============================================================================
// EMERGENCY INSTRUCTIONS
// =============================================================================

/// Pause new stakes (allows existing stakes to continue)
pub fn pause_new_stakes(
    global_pool: &mut GlobalPool,
    admin: &AdminAuthority,
    signer: &Signer,
) -> Result<()> {
    validate_emergency_authority(admin, signer)?;

    global_pool.is_paused = true;

    emit!(EmergencyEvent {
        action: EmergencyAction::PauseNewStakes,
        admin: signer.key(),
        timestamp: Clock::get()?.unix_timestamp,
        message: "New stakes paused".to_string(),
    });

    msg!("EMERGENCY: New stakes paused by {}", signer.key());
    Ok(())
}

/// Resume normal operations
pub fn unpause(
    global_pool: &mut GlobalPool,
    admin: &AdminAuthority,
    signer: &Signer,
) -> Result<()> {
    validate_critical_authority(admin, signer)?;

    global_pool.is_paused = false;
    global_pool.emergency_mode = false;

    emit!(EmergencyEvent {
        action: EmergencyAction::Resume,
        admin: signer.key(),
        timestamp: Clock::get()?.unix_timestamp,
        message: "Normal operations resumed".to_string(),
    });

    msg!("EMERGENCY: Normal operations resumed by {}", signer.key());
    Ok(())
}

/// Enable emergency mode (allows instant unstake without cooldown)
pub fn enable_emergency_mode(
    global_pool: &mut GlobalPool,
    admin: &AdminAuthority,
    signer: &Signer,
) -> Result<()> {
    validate_emergency_authority(admin, signer)?;

    global_pool.is_paused = true;
    global_pool.emergency_mode = true;

    emit!(EmergencyEvent {
        action: EmergencyAction::EnableEmergencyMode,
        admin: signer.key(),
        timestamp: Clock::get()?.unix_timestamp,
        message: "Emergency mode enabled - instant unstake available".to_string(),
    });

    msg!("EMERGENCY: Emergency mode enabled by {}", signer.key());
    Ok(())
}

/// Emergency unstake for a user (no cooldown, forfeits pending rewards)
pub fn emergency_unstake(
    global_pool: &mut GlobalPool,
    user_stake: &mut UserStake,
    user: &Signer,
) -> Result<u64> {
    require!(
        global_pool.emergency_mode,
        EmergencyError::NotInEmergencyMode
    );
    require!(
        user_stake.owner == user.key(),
        EmergencyError::Unauthorized
    );

    let amount = user_stake.staked_amount;

    // Reset user stake
    user_stake.staked_amount = 0;
    user_stake.pending_rewards = 0;  // Forfeited in emergency

    // Update global stats
    global_pool.total_staked = global_pool.total_staked.saturating_sub(amount);
    global_pool.total_stakers = global_pool.total_stakers.saturating_sub(1);

    emit!(EmergencyEvent {
        action: EmergencyAction::EmergencyUnstake,
        admin: user.key(),
        timestamp: Clock::get()?.unix_timestamp,
        message: format!("Emergency unstake of {} tokens", amount),
    });

    msg!("EMERGENCY: User {} emergency unstaked {} tokens", user.key(), amount);
    Ok(amount)
}

/// Admin emergency withdraw all funds (nuclear option)
pub fn admin_emergency_withdraw(
    global_pool: &mut GlobalPool,
    fee_vault: &mut FeeVault,
    admin: &AdminAuthority,
    signer: &Signer,
    destination: &Pubkey,
) -> Result<(u64, u64)> {
    // Requires primary admin
    validate_critical_authority(admin, signer)?;

    // Must be in full shutdown mode
    require!(
        global_pool.emergency_mode && global_pool.is_paused,
        EmergencyError::NotInEmergencyMode
    );

    let staked_amount = global_pool.total_staked;
    let vault_balance = fee_vault.pending_distribution;

    // Mark as withdrawn
    global_pool.total_staked = 0;
    global_pool.total_stakers = 0;
    fee_vault.pending_distribution = 0;

    emit!(EmergencyEvent {
        action: EmergencyAction::AdminWithdraw,
        admin: signer.key(),
        timestamp: Clock::get()?.unix_timestamp,
        message: format!(
            "Admin withdrew {} staked tokens and {} SOL to {}",
            staked_amount, vault_balance, destination
        ),
    });

    msg!(
        "EMERGENCY: Admin {} withdrew all funds to {}",
        signer.key(),
        destination
    );

    Ok((staked_amount, vault_balance))
}

// =============================================================================
// GRADUAL SHUTDOWN
// =============================================================================

/// Gradual shutdown state
#[account]
pub struct GradualShutdown {
    pub initiated_at: i64,
    pub shutdown_at: i64,  // When full shutdown happens
    pub allow_new_stakes: bool,
    pub allow_unstakes: bool,
    pub allow_claims: bool,
    pub reason: String,
    pub bump: u8,
}

impl GradualShutdown {
    pub const LEN: usize = 8 + 8 + 8 + 1 + 1 + 1 + 64 + 1;
}

/// Initiate gradual shutdown (7 day wind-down)
pub fn initiate_gradual_shutdown(
    global_pool: &mut GlobalPool,
    shutdown: &mut GradualShutdown,
    admin: &AdminAuthority,
    signer: &Signer,
    reason: String,
) -> Result<()> {
    validate_critical_authority(admin, signer)?;

    let now = Clock::get()?.unix_timestamp;
    let seven_days = 7 * 24 * 60 * 60;

    shutdown.initiated_at = now;
    shutdown.shutdown_at = now + seven_days;
    shutdown.allow_new_stakes = false;  // Immediately stop new stakes
    shutdown.allow_unstakes = true;      // Allow people to leave
    shutdown.allow_claims = true;        // Allow claiming earned rewards
    shutdown.reason = reason.clone();

    global_pool.is_paused = true;

    emit!(EmergencyEvent {
        action: EmergencyAction::GradualShutdown,
        admin: signer.key(),
        timestamp: now,
        message: format!("Gradual shutdown initiated. Reason: {}. Full shutdown at: {}", reason, shutdown.shutdown_at),
    });

    msg!("EMERGENCY: Gradual shutdown initiated. Full shutdown in 7 days.");
    Ok(())
}

// =============================================================================
// GUARD CLAUSES
// =============================================================================

/// Check if staking is allowed
pub fn require_staking_allowed(global_pool: &GlobalPool) -> Result<()> {
    require!(!global_pool.is_paused, EmergencyError::StakingPaused);
    require!(!global_pool.emergency_mode, EmergencyError::InEmergencyMode);
    Ok(())
}

/// Check if unstaking is allowed
pub fn require_unstaking_allowed(global_pool: &GlobalPool) -> Result<()> {
    // Unstaking is always allowed, but rules differ in emergency mode
    Ok(())
}

/// Check if claiming is allowed
pub fn require_claiming_allowed(global_pool: &GlobalPool) -> Result<()> {
    require!(!global_pool.emergency_mode, EmergencyError::InEmergencyMode);
    Ok(())
}

// =============================================================================
// AUTHORITY VALIDATION
// =============================================================================

fn validate_emergency_authority(
    admin: &AdminAuthority,
    signer: &Signer,
) -> Result<()> {
    require!(
        admin.can_emergency(&signer.key()),
        EmergencyError::Unauthorized
    );
    Ok(())
}

fn validate_critical_authority(
    admin: &AdminAuthority,
    signer: &Signer,
) -> Result<()> {
    require!(
        admin.can_critical(&signer.key()),
        EmergencyError::Unauthorized
    );
    Ok(())
}

// =============================================================================
// MULTISIG SUPPORT
// =============================================================================

/// Pending emergency action requiring multiple signatures
#[account]
pub struct PendingEmergencyAction {
    pub action: EmergencyAction,
    pub proposer: Pubkey,
    pub proposed_at: i64,
    pub expires_at: i64,
    pub approvals: Vec<Pubkey>,
    pub required_approvals: u8,
    pub executed: bool,
    pub bump: u8,
}

impl PendingEmergencyAction {
    pub const LEN: usize = 8 + 1 + 32 + 8 + 8 + (4 + 32 * 5) + 1 + 1 + 1;

    pub fn is_approved(&self) -> bool {
        self.approvals.len() >= self.required_approvals as usize
    }

    pub fn has_approved(&self, key: &Pubkey) -> bool {
        self.approvals.contains(key)
    }
}

/// Propose an emergency action
pub fn propose_emergency_action(
    pending: &mut PendingEmergencyAction,
    admin: &AdminAuthority,
    signer: &Signer,
    action: EmergencyAction,
) -> Result<()> {
    require!(admin.is_admin(&signer.key()), EmergencyError::Unauthorized);

    let now = Clock::get()?.unix_timestamp;

    pending.action = action;
    pending.proposer = signer.key();
    pending.proposed_at = now;
    pending.expires_at = now + (48 * 60 * 60);  // 48 hour expiry
    pending.approvals = vec![signer.key()];     // Proposer auto-approves
    pending.required_approvals = admin.required_signatures;
    pending.executed = false;

    emit!(EmergencyEvent {
        action: EmergencyAction::Propose,
        admin: signer.key(),
        timestamp: now,
        message: format!("Proposed emergency action: {:?}", action),
    });

    Ok(())
}

/// Approve a pending emergency action
pub fn approve_emergency_action(
    pending: &mut PendingEmergencyAction,
    admin: &AdminAuthority,
    signer: &Signer,
) -> Result<bool> {
    require!(admin.is_admin(&signer.key()), EmergencyError::Unauthorized);
    require!(!pending.executed, EmergencyError::AlreadyExecuted);
    require!(
        Clock::get()?.unix_timestamp < pending.expires_at,
        EmergencyError::ActionExpired
    );
    require!(
        !pending.has_approved(&signer.key()),
        EmergencyError::AlreadyApproved
    );

    pending.approvals.push(signer.key());

    emit!(EmergencyEvent {
        action: EmergencyAction::Approve,
        admin: signer.key(),
        timestamp: Clock::get()?.unix_timestamp,
        message: format!(
            "Approved action. {}/{} approvals",
            pending.approvals.len(),
            pending.required_approvals
        ),
    });

    Ok(pending.is_approved())
}

// =============================================================================
// EVENTS
// =============================================================================

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub enum EmergencyAction {
    PauseNewStakes,
    PauseAll,
    Resume,
    EnableEmergencyMode,
    EmergencyUnstake,
    AdminWithdraw,
    GradualShutdown,
    Propose,
    Approve,
    Execute,
}

#[event]
pub struct EmergencyEvent {
    pub action: EmergencyAction,
    pub admin: Pubkey,
    pub timestamp: i64,
    pub message: String,
}

// =============================================================================
// ERROR CODES
// =============================================================================

#[error_code]
pub enum EmergencyError {
    #[msg("Unauthorized for this emergency action")]
    Unauthorized,

    #[msg("Staking is currently paused")]
    StakingPaused,

    #[msg("System is in emergency mode")]
    InEmergencyMode,

    #[msg("Not in emergency mode")]
    NotInEmergencyMode,

    #[msg("Action already executed")]
    AlreadyExecuted,

    #[msg("Action has expired")]
    ActionExpired,

    #[msg("Already approved this action")]
    AlreadyApproved,

    #[msg("Insufficient approvals")]
    InsufficientApprovals,
}

// =============================================================================
// RECOVERY PROCEDURES
// =============================================================================

/// Recovery steps documentation
pub mod recovery {
    /// After emergency mode:
    /// 1. All users should emergency_unstake their tokens
    /// 2. Admin collects remaining funds
    /// 3. Deploy new contract with fixes
    /// 4. Airdrop to affected users from collected funds
    /// 5. Resume operations with new contract

    /// After gradual shutdown:
    /// 1. Users have 7 days to unstake normally
    /// 2. After deadline, remaining funds returned via admin_emergency_withdraw
    /// 3. Pro-rata distribution to remaining stakers off-chain

    /// Contract upgrade path:
    /// 1. Deploy new contract
    /// 2. Migrate state (read old, write new)
    /// 3. Point frontend to new contract
    /// 4. Close old contract accounts
}
