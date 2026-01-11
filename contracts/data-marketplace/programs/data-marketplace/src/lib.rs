use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("DmktXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX");

/// Data Marketplace Program
///
/// Features:
/// - List anonymized trade data packages
/// - Purchase data with SOL/USDC
/// - Revenue distribution to data contributors
/// - Wallet-based verification (no KYC)
/// - Category-based pricing
#[program]
pub mod data_marketplace {
    use super::*;

    /// Initialize the marketplace
    pub fn initialize(
        ctx: Context<Initialize>,
        fee_bps: u16,  // Platform fee in basis points (100 = 1%)
    ) -> Result<()> {
        let marketplace = &mut ctx.accounts.marketplace;

        marketplace.authority = ctx.accounts.authority.key();
        marketplace.treasury = ctx.accounts.treasury.key();
        marketplace.fee_bps = fee_bps;
        marketplace.total_listings = 0;
        marketplace.total_sales = 0;
        marketplace.total_volume = 0;
        marketplace.paused = false;
        marketplace.bump = ctx.bumps.marketplace;

        msg!("Marketplace initialized with {}bps fee", fee_bps);
        Ok(())
    }

    /// List a data package for sale
    pub fn list_data_package(
        ctx: Context<ListDataPackage>,
        ipfs_hash: String,
        category: DataCategory,
        price: u64,
        record_count: u64,
        description: String,
    ) -> Result<()> {
        require!(!ctx.accounts.marketplace.paused, MarketplaceError::MarketplacePaused);
        require!(price > 0, MarketplaceError::InvalidPrice);
        require!(record_count > 0, MarketplaceError::InvalidRecordCount);
        require!(ipfs_hash.len() == 46, MarketplaceError::InvalidIpfsHash);  // CIDv0 length
        require!(description.len() <= 256, MarketplaceError::DescriptionTooLong);

        let marketplace = &mut ctx.accounts.marketplace;
        let listing = &mut ctx.accounts.listing;
        let clock = Clock::get()?;

        listing.id = marketplace.total_listings;
        listing.seller = ctx.accounts.seller.key();
        listing.ipfs_hash = ipfs_hash.clone();
        listing.category = category;
        listing.price = price;
        listing.record_count = record_count;
        listing.description = description;
        listing.created_at = clock.unix_timestamp;
        listing.updated_at = clock.unix_timestamp;
        listing.sales_count = 0;
        listing.total_revenue = 0;
        listing.active = true;
        listing.bump = ctx.bumps.listing;

        marketplace.total_listings += 1;

        msg!("Listed data package {} with {} records at {} lamports",
            marketplace.total_listings - 1, record_count, price);

        emit!(ListingCreatedEvent {
            listing_id: listing.id,
            seller: ctx.accounts.seller.key(),
            category: category as u8,
            price,
            record_count,
            ipfs_hash,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Purchase a data package
    pub fn purchase_data(ctx: Context<PurchaseData>) -> Result<()> {
        require!(!ctx.accounts.marketplace.paused, MarketplaceError::MarketplacePaused);

        let listing = &mut ctx.accounts.listing;
        let marketplace = &mut ctx.accounts.marketplace;
        let clock = Clock::get()?;

        require!(listing.active, MarketplaceError::ListingNotActive);

        let price = listing.price;

        // Calculate fees
        let platform_fee = (price as u128)
            .checked_mul(marketplace.fee_bps as u128)
            .ok_or(MarketplaceError::Overflow)?
            .checked_div(10000)
            .ok_or(MarketplaceError::Overflow)? as u64;

        let seller_amount = price.checked_sub(platform_fee)
            .ok_or(MarketplaceError::Overflow)?;

        // Transfer payment to seller
        let ix_seller = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.buyer.key(),
            &ctx.accounts.seller.key(),
            seller_amount,
        );
        anchor_lang::solana_program::program::invoke(
            &ix_seller,
            &[
                ctx.accounts.buyer.to_account_info(),
                ctx.accounts.seller.to_account_info(),
            ],
        )?;

        // Transfer platform fee to treasury
        if platform_fee > 0 {
            let ix_fee = anchor_lang::solana_program::system_instruction::transfer(
                &ctx.accounts.buyer.key(),
                &ctx.accounts.treasury.key(),
                platform_fee,
            );
            anchor_lang::solana_program::program::invoke(
                &ix_fee,
                &[
                    ctx.accounts.buyer.to_account_info(),
                    ctx.accounts.treasury.to_account_info(),
                ],
            )?;
        }

        // Record purchase
        let purchase = &mut ctx.accounts.purchase;
        purchase.buyer = ctx.accounts.buyer.key();
        purchase.listing = listing.key();
        purchase.listing_id = listing.id;
        purchase.price_paid = price;
        purchase.purchased_at = clock.unix_timestamp;
        purchase.bump = ctx.bumps.purchase;

        // Update listing stats
        listing.sales_count += 1;
        listing.total_revenue = listing.total_revenue.checked_add(seller_amount)
            .ok_or(MarketplaceError::Overflow)?;

        // Update marketplace stats
        marketplace.total_sales += 1;
        marketplace.total_volume = marketplace.total_volume.checked_add(price)
            .ok_or(MarketplaceError::Overflow)?;

        msg!("Purchased listing {} for {} lamports (fee: {})",
            listing.id, price, platform_fee);

        emit!(PurchaseEvent {
            listing_id: listing.id,
            buyer: ctx.accounts.buyer.key(),
            seller: listing.seller,
            price,
            platform_fee,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Update listing price
    pub fn update_listing_price(
        ctx: Context<UpdateListing>,
        new_price: u64,
    ) -> Result<()> {
        require!(new_price > 0, MarketplaceError::InvalidPrice);

        let listing = &mut ctx.accounts.listing;
        let clock = Clock::get()?;

        let old_price = listing.price;
        listing.price = new_price;
        listing.updated_at = clock.unix_timestamp;

        msg!("Updated listing {} price from {} to {}", listing.id, old_price, new_price);

        Ok(())
    }

    /// Deactivate a listing
    pub fn deactivate_listing(ctx: Context<UpdateListing>) -> Result<()> {
        let listing = &mut ctx.accounts.listing;
        let clock = Clock::get()?;

        listing.active = false;
        listing.updated_at = clock.unix_timestamp;

        msg!("Deactivated listing {}", listing.id);

        emit!(ListingDeactivatedEvent {
            listing_id: listing.id,
            seller: listing.seller,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Reactivate a listing
    pub fn reactivate_listing(ctx: Context<UpdateListing>) -> Result<()> {
        let listing = &mut ctx.accounts.listing;
        let clock = Clock::get()?;

        listing.active = true;
        listing.updated_at = clock.unix_timestamp;

        msg!("Reactivated listing {}", listing.id);

        Ok(())
    }

    /// Update platform fee (admin only)
    pub fn update_fee(ctx: Context<AdminUpdate>, new_fee_bps: u16) -> Result<()> {
        require!(new_fee_bps <= 1000, MarketplaceError::FeeTooHigh);  // Max 10%

        let marketplace = &mut ctx.accounts.marketplace;
        let old_fee = marketplace.fee_bps;
        marketplace.fee_bps = new_fee_bps;

        msg!("Updated fee from {}bps to {}bps", old_fee, new_fee_bps);

        Ok(())
    }

    /// Pause marketplace (admin only)
    pub fn pause(ctx: Context<AdminUpdate>) -> Result<()> {
        let marketplace = &mut ctx.accounts.marketplace;
        marketplace.paused = true;

        msg!("Marketplace paused");

        Ok(())
    }

    /// Unpause marketplace (admin only)
    pub fn unpause(ctx: Context<AdminUpdate>) -> Result<()> {
        let marketplace = &mut ctx.accounts.marketplace;
        marketplace.paused = false;

        msg!("Marketplace unpaused");

        Ok(())
    }

    /// Withdraw treasury funds (admin only)
    pub fn withdraw_treasury(
        ctx: Context<WithdrawTreasury>,
        amount: u64,
    ) -> Result<()> {
        require!(amount > 0, MarketplaceError::InvalidAmount);

        // Transfer from treasury to recipient
        **ctx.accounts.treasury.to_account_info().try_borrow_mut_lamports()? -= amount;
        **ctx.accounts.recipient.to_account_info().try_borrow_mut_lamports()? += amount;

        msg!("Withdrew {} lamports from treasury", amount);

        Ok(())
    }
}

// =============================================================================
// Data Types
// =============================================================================

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq)]
pub enum DataCategory {
    TradeOutcomes = 0,      // Win/loss data by strategy
    StrategySignals = 1,    // Entry/exit signals
    MarketTiming = 2,       // Timing patterns
    RiskProfile = 3,        // Risk metrics
    WhaleMoves = 4,         // Whale transaction data
    SentimentData = 5,      // Social sentiment
    OnChainMetrics = 6,     // On-chain analytics
    Custom = 7,             // Custom category
}

// =============================================================================
// Accounts
// =============================================================================

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + Marketplace::INIT_SPACE,
        seeds = [b"marketplace"],
        bump
    )]
    pub marketplace: Account<'info, Marketplace>,

    /// CHECK: Treasury PDA for holding fees
    #[account(
        seeds = [b"treasury"],
        bump
    )]
    pub treasury: AccountInfo<'info>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(ipfs_hash: String)]
pub struct ListDataPackage<'info> {
    #[account(mut)]
    pub marketplace: Account<'info, Marketplace>,

    #[account(
        init,
        payer = seller,
        space = 8 + DataListing::INIT_SPACE,
        seeds = [b"listing", marketplace.key().as_ref(), &marketplace.total_listings.to_le_bytes()],
        bump
    )]
    pub listing: Account<'info, DataListing>,

    #[account(mut)]
    pub seller: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct PurchaseData<'info> {
    #[account(mut)]
    pub marketplace: Account<'info, Marketplace>,

    #[account(
        mut,
        constraint = listing.active @ MarketplaceError::ListingNotActive
    )]
    pub listing: Account<'info, DataListing>,

    #[account(
        init,
        payer = buyer,
        space = 8 + Purchase::INIT_SPACE,
        seeds = [b"purchase", listing.key().as_ref(), buyer.key().as_ref()],
        bump
    )]
    pub purchase: Account<'info, Purchase>,

    /// CHECK: Seller receives payment
    #[account(
        mut,
        constraint = seller.key() == listing.seller @ MarketplaceError::InvalidSeller
    )]
    pub seller: AccountInfo<'info>,

    /// CHECK: Treasury receives platform fee
    #[account(
        mut,
        seeds = [b"treasury"],
        bump
    )]
    pub treasury: AccountInfo<'info>,

    #[account(mut)]
    pub buyer: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdateListing<'info> {
    pub marketplace: Account<'info, Marketplace>,

    #[account(
        mut,
        constraint = listing.seller == seller.key() @ MarketplaceError::Unauthorized
    )]
    pub listing: Account<'info, DataListing>,

    pub seller: Signer<'info>,
}

#[derive(Accounts)]
pub struct AdminUpdate<'info> {
    #[account(
        mut,
        constraint = marketplace.authority == authority.key() @ MarketplaceError::Unauthorized
    )]
    pub marketplace: Account<'info, Marketplace>,

    pub authority: Signer<'info>,
}

#[derive(Accounts)]
pub struct WithdrawTreasury<'info> {
    #[account(
        constraint = marketplace.authority == authority.key() @ MarketplaceError::Unauthorized
    )]
    pub marketplace: Account<'info, Marketplace>,

    /// CHECK: Treasury PDA
    #[account(
        mut,
        seeds = [b"treasury"],
        bump
    )]
    pub treasury: AccountInfo<'info>,

    /// CHECK: Recipient of withdrawal
    #[account(mut)]
    pub recipient: AccountInfo<'info>,

    pub authority: Signer<'info>,
}

// =============================================================================
// State
// =============================================================================

#[account]
#[derive(InitSpace)]
pub struct Marketplace {
    pub authority: Pubkey,
    pub treasury: Pubkey,
    pub fee_bps: u16,
    pub total_listings: u64,
    pub total_sales: u64,
    pub total_volume: u64,
    pub paused: bool,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct DataListing {
    pub id: u64,
    pub seller: Pubkey,
    #[max_len(46)]
    pub ipfs_hash: String,
    pub category: DataCategory,
    pub price: u64,
    pub record_count: u64,
    #[max_len(256)]
    pub description: String,
    pub created_at: i64,
    pub updated_at: i64,
    pub sales_count: u64,
    pub total_revenue: u64,
    pub active: bool,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Purchase {
    pub buyer: Pubkey,
    pub listing: Pubkey,
    pub listing_id: u64,
    pub price_paid: u64,
    pub purchased_at: i64,
    pub bump: u8,
}

// =============================================================================
// Events
// =============================================================================

#[event]
pub struct ListingCreatedEvent {
    pub listing_id: u64,
    pub seller: Pubkey,
    pub category: u8,
    pub price: u64,
    pub record_count: u64,
    pub ipfs_hash: String,
    pub timestamp: i64,
}

#[event]
pub struct PurchaseEvent {
    pub listing_id: u64,
    pub buyer: Pubkey,
    pub seller: Pubkey,
    pub price: u64,
    pub platform_fee: u64,
    pub timestamp: i64,
}

#[event]
pub struct ListingDeactivatedEvent {
    pub listing_id: u64,
    pub seller: Pubkey,
    pub timestamp: i64,
}

// =============================================================================
// Errors
// =============================================================================

#[error_code]
pub enum MarketplaceError {
    #[msg("Marketplace is paused")]
    MarketplacePaused,
    #[msg("Invalid price")]
    InvalidPrice,
    #[msg("Invalid record count")]
    InvalidRecordCount,
    #[msg("Invalid IPFS hash")]
    InvalidIpfsHash,
    #[msg("Description too long")]
    DescriptionTooLong,
    #[msg("Listing not active")]
    ListingNotActive,
    #[msg("Invalid seller")]
    InvalidSeller,
    #[msg("Fee too high (max 10%)")]
    FeeTooHigh,
    #[msg("Invalid amount")]
    InvalidAmount,
    #[msg("Unauthorized")]
    Unauthorized,
    #[msg("Arithmetic overflow")]
    Overflow,
}
