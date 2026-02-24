import asyncio
from core.security.key_manager import KeyManager
from bots.alvara_manager.client import MockWeb3Client
from bots.alvara_manager.grok_allocator import GrokAllocator

async def run_alvara_rebalance(narrative: str):
    print("--- Booting Alvara Protocol (ERC-7621) EVM Proxy ---")

    # 1. EVM context creation
    km = KeyManager()
    wallet = km.load_wallet(name="Alvara_EVM_Wallet_1")
    evm_client = MockWeb3Client(wallet)

    # 2. Intel Ingestion
    print(f"[{'GROK'}] Evaluating Narrative Stream: '{narrative}'")
    allocator = GrokAllocator()

    # Mathematical gating via pydantic guarantees correct percentages
    try:
        basket = await allocator.determine_optimal_basket(narrative)
    except ValueError as e:
        print(f"[REJECTED] {e}")
        return

    print(f"[{'GROK'}] Validated Allocations: {basket.allocations}")

    # 3. Execution against ERC-7621 ABI
    signed_payload = evm_client.build_erc7621_mint(basket.allocations)
    print("[RUNNER] Signed payload generated locally.")

    result = evm_client.send_raw_transaction(signed_payload)
    print(f"[RUNNER] Transmitted to Ethereum Mainnet. Status: {result}")

if __name__ == "__main__":
    asyncio.run(run_alvara_rebalance("DeFi is booming big time right now!"))
