"""
Example: Using Transaction Verification System

Demonstrates how to use the new transaction confirmation service
with the Jarvis treasury trading system.
"""

import asyncio
from bots.treasury.jupiter import JupiterClient
from core.security.tx_confirmation import (
    TransactionConfirmationService,
    CommitmentLevel,
    TransactionStatus
)


async def example_swap_with_verification():
    """Example: Execute a swap with automatic verification."""

    # JupiterClient now includes automatic verification
    client = JupiterClient()

    try:
        # Get a quote
        quote = await client.get_quote(
            input_mint=client.SOL_MINT,
            output_mint=client.USDC_MINT,
            amount=1.0  # 1 SOL
        )

        if not quote:
            print("Failed to get quote")
            return

        print(f"Quote: {quote.input_amount_ui} {quote.input_symbol} -> "
              f"{quote.output_amount_ui} {quote.output_symbol}")

        # Execute swap - now includes automatic on-chain verification
        from bots.treasury.wallet import SecureWallet
        wallet = SecureWallet()

        result = await client.execute_swap(quote, wallet)

        if result.success:
            print(f"\n✅ Transaction CONFIRMED on-chain!")
            print(f"Signature: {result.signature}")
            print(f"Swapped {result.input_amount} {result.input_symbol} "
                  f"for {result.output_amount} {result.output_symbol}")
        else:
            print(f"\n❌ Transaction FAILED: {result.error}")

    finally:
        await client.close()


async def example_manual_verification():
    """Example: Manual transaction verification."""

    # Create confirmation service
    service = TransactionConfirmationService(
        rpc_url="https://api.mainnet-beta.solana.com",
        commitment=CommitmentLevel.CONFIRMED
    )

    try:
        # Verify a specific transaction
        signature = "YOUR_TRANSACTION_SIGNATURE_HERE"

        print(f"Verifying transaction: {signature[:12]}...")
        result = await service.verify_transaction(signature)

        if result.success:
            print(f"\n✅ Transaction confirmed!")
            print(f"Status: {result.status.value}")
            print(f"Slot: {result.slot}")
            print(f"Confirmations: {result.confirmations}")
            print(f"Verification time: {result.verification_time_ms:.0f}ms")
            print(f"Retry count: {result.retry_count}")
        else:
            print(f"\n❌ Transaction failed!")
            print(f"Status: {result.status.value}")
            print(f"Error: {result.error}")

    finally:
        await service.close()


async def example_transaction_history():
    """Example: Access transaction history."""

    from core.security.tx_confirmation import get_confirmation_service

    service = get_confirmation_service(
        rpc_url="https://api.mainnet-beta.solana.com"
    )

    try:
        # Get recent transactions
        print("Recent transactions:")
        history = await service.get_transaction_history(limit=10)

        for entry in history:
            status_emoji = "✅" if entry.status == TransactionStatus.CONFIRMED else "❌"
            print(f"{status_emoji} {entry.signature[:12]}... - {entry.status.value}")
            print(f"   {entry.input_amount} -> {entry.output_amount}")
            print(f"   Verified in {entry.verification_time_ms:.0f}ms "
                  f"({entry.retry_count} retries)")

        # Get failed transactions
        print("\n\nFailed transactions:")
        failed = await service.get_failed_transactions(limit=5)

        for entry in failed:
            print(f"❌ {entry.signature[:12]}... - {entry.error}")

    finally:
        await service.close()


async def example_custom_commitment():
    """Example: Using different commitment levels."""

    from bots.treasury.jupiter import JupiterClient

    # For fast confirmation (less secure)
    service_fast = TransactionConfirmationService(
        rpc_url="https://api.mainnet-beta.solana.com",
        commitment=CommitmentLevel.PROCESSED  # ~400ms
    )

    # For maximum security (slower)
    service_secure = TransactionConfirmationService(
        rpc_url="https://api.mainnet-beta.solana.com",
        commitment=CommitmentLevel.FINALIZED  # ~30s
    )

    signature = "YOUR_TRANSACTION_SIGNATURE_HERE"

    try:
        # Fast verification
        print("Fast verification (PROCESSED)...")
        result_fast = await service_fast.verify_transaction(signature)
        print(f"Result: {result_fast.status.value} "
              f"in {result_fast.verification_time_ms:.0f}ms")

        # Secure verification
        print("\nSecure verification (FINALIZED)...")
        result_secure = await service_secure.verify_transaction(signature)
        print(f"Result: {result_secure.status.value} "
              f"in {result_secure.verification_time_ms:.0f}ms")

    finally:
        await service_fast.close()
        await service_secure.close()


async def example_with_alerts():
    """Example: Using alert callbacks for failed transactions."""

    async def alert_handler(result):
        """Called when transaction fails."""
        print(f"\n🚨 ALERT: Transaction failed!")
        print(f"Signature: {result.signature}")
        print(f"Error: {result.error}")
        print(f"Retry count: {result.retry_count}")

        # Could send Telegram message, email, etc.

    service = TransactionConfirmationService(
        rpc_url="https://api.mainnet-beta.solana.com",
        commitment=CommitmentLevel.CONFIRMED,
        alert_callback=alert_handler  # Register callback
    )

    try:
        signature = "YOUR_TRANSACTION_SIGNATURE_HERE"
        result = await service.verify_transaction(signature)

        # If transaction fails, alert_handler will be called automatically

    finally:
        await service.close()


if __name__ == '__main__':
    print("Transaction Verification Examples\n")

    print("1. Swap with automatic verification")
    # asyncio.run(example_swap_with_verification())

    print("\n2. Manual verification")
    # asyncio.run(example_manual_verification())

    print("\n3. Transaction history")
    # asyncio.run(example_transaction_history())

    print("\n4. Custom commitment levels")
    # asyncio.run(example_custom_commitment())

    print("\n5. Alert callbacks")
    # asyncio.run(example_with_alerts())

    print("\n(Uncomment examples to run)")
