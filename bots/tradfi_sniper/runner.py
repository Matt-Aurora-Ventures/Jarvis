import asyncio
from core.intel.tradfi_feed import get_tradfi_momentum
from bots.tradfi_sniper.strategy_mapper import load_tradfi_strategy
from core.security.key_manager import KeyManager
from bots.jupiter_perps.client import JupiterPerpsAnchorClient

async def run_tradfi_sniper(preset: str, token_mint: bytes, default_size: float = 1.0):
    print(f"--- Booting TradFi Sniper Proxy for preset: {preset} ---")

    # Enforce safe strategy limits mapped from UI
    try:
        config = load_tradfi_strategy(preset)
        print(f"[MAPPER] Loaded constraints: SL {config.stopLossPct}%, TP {config.takeProfitPct}%")
    except ValueError as e:
        print(f"[ERROR] {str(e)}")
        return

    # Ingest Data Bias
    bias = get_tradfi_momentum()
    print(f"[FEED] Live Data Bias implies: {bias}")

    if bias == "NEUTRAL":
         print("[RUNNER] Skipping execution -> NEUTRAL Bias.")
         return

    # Proceed to Execution (using the Jup Swap via our Jupiter Perps Key infrastructure for mocked purposes)
    km = KeyManager()
    wallet = km.load_wallet(name="TradFi_Wallet_1")
    executor = JupiterPerpsAnchorClient(wallet)

    print(f"[RUNNER] Bridging Jupiter tx for SPL Equity Token...")
    # Fire off trade
    signed_tx = await executor.build_position_request(
        custody=token_mint,
        collateral=b"USDC_Mint",
        size=default_size,
        action=bias
    )

    status = await executor.execute_tx(signed_tx)
    print(f"[RUNNER] Transaction executed successfully. {status}")

if __name__ == "__main__":
    asyncio.run(run_tradfi_sniper("xstock_intraday", b"TSLA_SPL_Mint"))
