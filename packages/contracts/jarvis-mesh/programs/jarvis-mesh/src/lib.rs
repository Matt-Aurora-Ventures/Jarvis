use anchor_lang::prelude::*;

declare_id!("Jarv1sMesh111111111111111111111111111111111");

#[program]
pub mod jarvis_mesh {
    use super::*;

    pub fn initialize_mesh(ctx: Context<InitializeMesh>, authority: Pubkey) -> Result<()> {
        let mesh = &mut ctx.accounts.mesh;
        mesh.authority = authority;
        mesh.bump = ctx.bumps.mesh;
        Ok(())
    }

    pub fn register_node(ctx: Context<RegisterNode>, node_id: String, endpoint: String) -> Result<()> {
        let node = &mut ctx.accounts.node;
        node.node_id = node_id;
        node.endpoint = endpoint;
        node.bump = ctx.bumps.node;
        Ok(())
    }

    pub fn submit_consensus(ctx: Context<SubmitConsensus>, request_id: String, winner: String, confidence_bps: u16) -> Result<()> {
        let consensus = &mut ctx.accounts.consensus;
        consensus.request_id = request_id;
        consensus.winner = winner;
        consensus.confidence_bps = confidence_bps;
        consensus.bump = ctx.bumps.consensus;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct InitializeMesh<'info> {
    #[account(init, payer = payer, space = 8 + 32 + 1, seeds = [b"mesh"], bump)]
    pub mesh: Account<'info, MeshState>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RegisterNode<'info> {
    #[account(init, payer = payer, space = 8 + 4 + 64 + 4 + 128 + 1, seeds = [b"node", node_id.as_bytes()], bump)]
    pub node: Account<'info, NodeState>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SubmitConsensus<'info> {
    #[account(init, payer = payer, space = 8 + 4 + 64 + 4 + 64 + 2 + 1, seeds = [b"consensus", request_id.as_bytes()], bump)]
    pub consensus: Account<'info, ConsensusState>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct MeshState {
    pub authority: Pubkey,
    pub bump: u8,
}

#[account]
pub struct NodeState {
    pub node_id: String,
    pub endpoint: String,
    pub bump: u8,
}

#[account]
pub struct ConsensusState {
    pub request_id: String,
    pub winner: String,
    pub confidence_bps: u16,
    pub bump: u8,
}
