/**
 * CPI (Cross-Program Invocation) Handlers
 * Prompt #33: Safe CPI calls for transfers and external program interactions
 */

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};
use anchor_spl::associated_token::AssociatedToken;

// =============================================================================
// SOL TRANSFER CPI
// =============================================================================

/// Transfer SOL from a PDA to a user
pub fn transfer_sol_from_pda<'info>(
    from_pda: AccountInfo<'info>,
    to_user: AccountInfo<'info>,
    amount: u64,
    seeds: &[&[u8]],
) -> Result<()> {
    // Verify we have enough balance
    let from_balance = from_pda.lamports();
    require!(from_balance >= amount, ErrorCode::InsufficientFunds);

    // Calculate rent-exempt minimum
    let rent = Rent::get()?;
    let min_balance = rent.minimum_balance(from_pda.data_len());
    require!(
        from_balance.saturating_sub(amount) >= min_balance,
        ErrorCode::InsufficientFunds
    );

    // Perform the transfer using invoke_signed
    let ix = anchor_lang::solana_program::system_instruction::transfer(
        from_pda.key,
        to_user.key,
        amount,
    );

    anchor_lang::solana_program::program::invoke_signed(
        &ix,
        &[from_pda, to_user],
        &[seeds],
    )?;

    msg!("Transferred {} lamports to user", amount);
    Ok(())
}

/// Transfer SOL from user to PDA (for deposits)
pub fn transfer_sol_to_pda<'info>(
    from_user: AccountInfo<'info>,
    to_pda: AccountInfo<'info>,
    system_program: AccountInfo<'info>,
    amount: u64,
) -> Result<()> {
    let ix = anchor_lang::solana_program::system_instruction::transfer(
        from_user.key,
        to_pda.key,
        amount,
    );

    anchor_lang::solana_program::program::invoke(
        &ix,
        &[from_user, to_pda, system_program],
    )?;

    msg!("Deposited {} lamports to PDA", amount);
    Ok(())
}

// =============================================================================
// SPL TOKEN TRANSFER CPI
// =============================================================================

/// Transfer SPL tokens from user to vault (staking)
pub fn transfer_tokens_to_vault<'info>(
    from_user_ata: AccountInfo<'info>,
    to_vault: AccountInfo<'info>,
    authority: AccountInfo<'info>,
    token_program: AccountInfo<'info>,
    amount: u64,
) -> Result<()> {
    let cpi_accounts = Transfer {
        from: from_user_ata,
        to: to_vault,
        authority,
    };

    let cpi_ctx = CpiContext::new(token_program, cpi_accounts);
    token::transfer(cpi_ctx, amount)?;

    msg!("Transferred {} tokens to vault", amount);
    Ok(())
}

/// Transfer SPL tokens from vault to user (unstaking)
pub fn transfer_tokens_from_vault<'info>(
    from_vault: AccountInfo<'info>,
    to_user_ata: AccountInfo<'info>,
    vault_authority: AccountInfo<'info>,
    token_program: AccountInfo<'info>,
    amount: u64,
    seeds: &[&[u8]],
) -> Result<()> {
    let cpi_accounts = Transfer {
        from: from_vault,
        to: to_user_ata,
        authority: vault_authority,
    };

    let cpi_ctx = CpiContext::new_with_signer(
        token_program,
        cpi_accounts,
        &[seeds],
    );

    token::transfer(cpi_ctx, amount)?;

    msg!("Transferred {} tokens from vault", amount);
    Ok(())
}

// =============================================================================
// JUPITER/BAGS SWAP CPI (for auto-compound)
// =============================================================================

/// Jupiter swap instruction data format
#[derive(AnchorSerialize, AnchorDeserialize)]
pub struct SwapParams {
    pub amount_in: u64,
    pub minimum_amount_out: u64,
    pub slippage_bps: u16,
}

/// Execute swap via Jupiter (simplified - actual implementation would use Jupiter SDK)
pub fn execute_jupiter_swap<'info>(
    jupiter_program: AccountInfo<'info>,
    user_source_ata: AccountInfo<'info>,
    user_dest_ata: AccountInfo<'info>,
    authority: AccountInfo<'info>,
    remaining_accounts: &[AccountInfo<'info>],
    params: SwapParams,
    seeds: &[&[u8]],
) -> Result<u64> {
    // Build Jupiter swap instruction
    // Note: This is a simplified version. Production would use Jupiter SDK.

    msg!("Executing swap: {} tokens with {} bps slippage",
        params.amount_in, params.slippage_bps);

    // In production, construct the actual Jupiter instruction
    // using the jupiter-swap-api crate or direct instruction building

    // Placeholder return - actual implementation would return actual amount received
    Ok(params.minimum_amount_out)
}

/// Execute swap via Bags.fm API (for partner fee earning)
pub fn execute_bags_swap<'info>(
    bags_program: AccountInfo<'info>,
    user_source_ata: AccountInfo<'info>,
    user_dest_ata: AccountInfo<'info>,
    authority: AccountInfo<'info>,
    partner_config: AccountInfo<'info>,
    remaining_accounts: &[AccountInfo<'info>],
    params: SwapParams,
    seeds: &[&[u8]],
) -> Result<u64> {
    msg!("Executing Bags swap: {} tokens", params.amount_in);

    // Bags swap would earn partner fees
    // Actual implementation would use Bags SDK

    Ok(params.minimum_amount_out)
}

// =============================================================================
// METAPLEX CPI (for governance token minting)
// =============================================================================

/// Mint governance tokens (gKR8TIV) when user stakes
pub fn mint_governance_tokens<'info>(
    mint: AccountInfo<'info>,
    to_ata: AccountInfo<'info>,
    mint_authority: AccountInfo<'info>,
    token_program: AccountInfo<'info>,
    amount: u64,
    seeds: &[&[u8]],
) -> Result<()> {
    let cpi_accounts = anchor_spl::token::MintTo {
        mint,
        to: to_ata,
        authority: mint_authority,
    };

    let cpi_ctx = CpiContext::new_with_signer(
        token_program,
        cpi_accounts,
        &[seeds],
    );

    anchor_spl::token::mint_to(cpi_ctx, amount)?;

    msg!("Minted {} governance tokens", amount);
    Ok(())
}

/// Burn governance tokens (gKR8TIV) when user unstakes
pub fn burn_governance_tokens<'info>(
    mint: AccountInfo<'info>,
    from_ata: AccountInfo<'info>,
    authority: AccountInfo<'info>,
    token_program: AccountInfo<'info>,
    amount: u64,
) -> Result<()> {
    let cpi_accounts = anchor_spl::token::Burn {
        mint,
        from: from_ata,
        authority,
    };

    let cpi_ctx = CpiContext::new(token_program, cpi_accounts);
    anchor_spl::token::burn(cpi_ctx, amount)?;

    msg!("Burned {} governance tokens", amount);
    Ok(())
}

// =============================================================================
// ERROR CODES
// =============================================================================

#[error_code]
pub enum ErrorCode {
    #[msg("Insufficient funds for transfer")]
    InsufficientFunds,

    #[msg("Slippage tolerance exceeded")]
    SlippageExceeded,

    #[msg("Invalid token account")]
    InvalidTokenAccount,

    #[msg("Unauthorized signer")]
    Unauthorized,

    #[msg("Swap failed")]
    SwapFailed,

    #[msg("CPI call failed")]
    CpiError,
}

// =============================================================================
// SAFE CPI WRAPPER
// =============================================================================

/// Wrapper for safe CPI calls with error handling
pub struct SafeCpi;

impl SafeCpi {
    /// Execute a CPI with error handling and logging
    pub fn execute<F, T>(operation: &str, f: F) -> Result<T>
    where
        F: FnOnce() -> Result<T>,
    {
        msg!("Executing CPI: {}", operation);

        match f() {
            Ok(result) => {
                msg!("CPI {} succeeded", operation);
                Ok(result)
            }
            Err(e) => {
                msg!("CPI {} failed: {:?}", operation, e);
                Err(e)
            }
        }
    }

    /// Execute with retry (for transient failures)
    pub fn execute_with_retry<F, T>(operation: &str, max_retries: u8, f: F) -> Result<T>
    where
        F: Fn() -> Result<T>,
    {
        let mut attempts = 0;
        loop {
            attempts += 1;
            match f() {
                Ok(result) => return Ok(result),
                Err(e) if attempts < max_retries => {
                    msg!("CPI {} attempt {} failed, retrying...", operation, attempts);
                    continue;
                }
                Err(e) => {
                    msg!("CPI {} failed after {} attempts", operation, attempts);
                    return Err(e);
                }
            }
        }
    }
}

// =============================================================================
// VALIDATION HELPERS
// =============================================================================

/// Validate that an account is owned by expected program
pub fn validate_account_owner(account: &AccountInfo, expected_owner: &Pubkey) -> Result<()> {
    require!(
        account.owner == expected_owner,
        ErrorCode::InvalidTokenAccount
    );
    Ok(())
}

/// Validate token account has expected mint
pub fn validate_token_account_mint(
    token_account: &Account<TokenAccount>,
    expected_mint: &Pubkey,
) -> Result<()> {
    require!(
        &token_account.mint == expected_mint,
        ErrorCode::InvalidTokenAccount
    );
    Ok(())
}

/// Validate signer is authorized
pub fn validate_signer(signer: &Signer, authorized: &Pubkey) -> Result<()> {
    require!(
        signer.key() == *authorized,
        ErrorCode::Unauthorized
    );
    Ok(())
}
