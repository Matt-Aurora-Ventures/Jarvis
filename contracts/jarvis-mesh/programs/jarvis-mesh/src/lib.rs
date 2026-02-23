use anchor_lang::prelude::*;

declare_id!("Jarv1sMesh111111111111111111111111111111111");

#[program]
pub mod jarvis_mesh {
    use super::*;

    pub fn register_node(
        ctx: Context<RegisterNode>,
        endpoint: String,
        stake_lamports: u64,
    ) -> Result<()> {
        require!(!endpoint.is_empty(), MeshError::InvalidEndpoint);
        require!(endpoint.len() <= 256, MeshError::InvalidEndpoint);

        let node = &mut ctx.accounts.node_registry;
        node.authority = ctx.accounts.authority.key();
        node.endpoint = endpoint;
        node.stake_lamports = stake_lamports;
        node.bump = ctx.bumps.node_registry;
        Ok(())
    }

    pub fn commit_state_hash(
        ctx: Context<CommitStateHash>,
        state_hash: [u8; 32],
    ) -> Result<()> {
        let commitment = &mut ctx.accounts.state_commitment;
        commitment.node = ctx.accounts.node_registry.key();
        commitment.state_hash = state_hash;
        commitment.slot = Clock::get()?.slot;
        commitment.bump = ctx.bumps.state_commitment;
        Ok(())
    }

    pub fn verify_context(
        ctx: Context<VerifyContext>,
        expected_hash: [u8; 32],
    ) -> Result<()> {
        require!(
            ctx.accounts.state_commitment.state_hash == expected_hash,
            MeshError::HashMismatch
        );
        Ok(())
    }
}

#[derive(Accounts)]
pub struct RegisterNode<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        init,
        payer = authority,
        space = NodeRegistry::LEN,
        seeds = [b"node", authority.key().as_ref()],
        bump
    )]
    pub node_registry: Account<'info, NodeRegistry>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct CommitStateHash<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        mut,
        seeds = [b"node", authority.key().as_ref()],
        bump = node_registry.bump,
        has_one = authority
    )]
    pub node_registry: Account<'info, NodeRegistry>,

    #[account(
        init,
        payer = authority,
        space = StateCommitment::LEN,
        seeds = [b"commitment", node_registry.key().as_ref()],
        bump
    )]
    pub state_commitment: Account<'info, StateCommitment>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct VerifyContext<'info> {
    pub node_registry: Account<'info, NodeRegistry>,

    #[account(
        seeds = [b"commitment", node_registry.key().as_ref()],
        bump = state_commitment.bump
    )]
    pub state_commitment: Account<'info, StateCommitment>,
}

#[account]
pub struct NodeRegistry {
    pub authority: Pubkey,
    pub endpoint: String,
    pub stake_lamports: u64,
    pub bump: u8,
}

impl NodeRegistry {
    pub const LEN: usize = 8 + 32 + 4 + 256 + 8 + 1;
}

#[account]
pub struct StateCommitment {
    pub node: Pubkey,
    pub state_hash: [u8; 32],
    pub slot: u64,
    pub bump: u8,
}

impl StateCommitment {
    pub const LEN: usize = 8 + 32 + 32 + 8 + 1;
}

#[error_code]
pub enum MeshError {
    #[msg("Invalid endpoint")]
    InvalidEndpoint,
    #[msg("State hash mismatch")]
    HashMismatch,
}

