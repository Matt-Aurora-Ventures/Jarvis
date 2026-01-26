# Solana + Telegram Libraries - Quick Reference
## For MCP Memory Server Storage

---

## 🔑 Critical Program IDs & Addresses

### Solana Core Programs
```python
# Store these in MCP Memory for quick access
SYSTEM_PROGRAM = "11111111111111111111111111111111"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
MEMO_PROGRAM = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
```

### DEX Programs
```python
# Jupiter
JUPITER_V6_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
JUPITER_V6_API = "https://quote-api.jup.ag/v6"

# Raydium
RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CLMM = "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK"

# Meteora DLMM
METEORA_DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"

# OpenBook (Serum v3 successor)
OPENBOOK_V2 = "opnb2LAfJYbRMAHHvqjCwQxanZn7ReEHp1k81EohpZb"

# Orca Whirlpools
ORCA_WHIRLPOOL = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"

# BAGS.fm
BAGS_PROGRAM = "BAGSGuhFcxRJMcZQj51Hn6zbFWRxiMQNZLwNLs49proo"  # Verify latest
```

### Common Token Mints
```python
# Mainnet Tokens
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
JUP = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
RAY = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
```

---

## 📚 Python Library Cheat Sheet

### 1. solana-py (Core SDK)
```python
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.transaction import Transaction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price

# Quick Connection
async def connect_solana(rpc_url: str):
    client = AsyncClient(rpc_url, commitment=Confirmed)
    return client

# Send Transaction with Priority Fee
async def send_tx_with_priority(
    client: AsyncClient,
    tx: Transaction,
    signers: list[Keypair],
    priority_fee_microlamports: int = 10000
):
    # Add compute budget instructions
    tx.add(set_compute_unit_price(priority_fee_microlamports))
    tx.add(set_compute_unit_limit(200000))
    
    result = await client.send_transaction(tx, *signers)
    return result
```

**Key solana-py Methods**:
- `get_account_info()` - Fetch account data
- `get_balance()` - Check SOL balance
- `get_token_accounts_by_owner()` - Get SPL token accounts
- `send_transaction()` - Submit transaction
- `simulate_transaction()` - Dry-run before sending
- `get_signatures_for_address()` - Transaction history
- `get_transaction()` - Fetch transaction details

### 2. solders (Rust-backed primitives)
```python
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash

# Generate wallet
wallet = Keypair()
print(f"Pubkey: {wallet.pubkey()}")
print(f"Secret: {bytes(wallet).hex()}")

# Load from bytes
secret_bytes = bytes.fromhex("your_hex_key")
wallet = Keypair.from_bytes(secret_bytes)

# Create instruction
instruction = Instruction(
    program_id=Pubkey.from_string("program_id_here"),
    accounts=[
        AccountMeta(pubkey=wallet.pubkey(), is_signer=True, is_writable=True),
    ],
    data=b"instruction_data"
)
```

### 3. anchorpy (Anchor Program Client)
```python
from anchorpy import Provider, Wallet, Program
from solders.keypair import Keypair

# Load program
async def load_anchor_program(
    program_id: str,
    idl_path: str,
    wallet: Keypair,
    rpc_url: str
):
    provider = Provider(
        AsyncClient(rpc_url),
        Wallet(wallet)
    )
    
    with open(idl_path) as f:
        idl = json.load(f)
    
    program = Program(idl, Pubkey.from_string(program_id), provider)
    return program

# Call instruction
result = await program.rpc["initialize"](
    ctx=Context(
        accounts={
            "user": wallet.pubkey(),
            "system_program": SYS_PROGRAM_ID,
        },
        signers=[wallet]
    )
)
```

---

## 🤖 Telegram Bot Libraries

### 1. aiogram 3.x (Modern, Async)
```python
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Bot setup
bot = Bot(token="YOUR_BOT_TOKEN")
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Command handler
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Welcome!")

# FSM for multi-step interactions
class SwapStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_amount = State()
    confirming = State()

@router.message(Command("swap"))
async def start_swap(message: Message, state: FSMContext):
    await state.set_state(SwapStates.waiting_for_token)
    await message.answer("Which token to swap?")

@router.message(SwapStates.waiting_for_token)
async def token_selected(message: Message, state: FSMContext):
    await state.update_data(token=message.text)
    await state.set_state(SwapStates.waiting_for_amount)
    await message.answer("How much?")

# Inline keyboard
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Confirm Swap", callback_data="confirm")],
    [InlineKeyboardButton(text="Cancel", callback_data="cancel")]
])

@router.callback_query(F.data == "confirm")
async def confirm_swap(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.answer(f"Swapping {data['amount']} {data['token']}")
    await state.clear()

# Run bot
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**aiogram Key Features**:
- Full async/await support
- FSM (Finite State Machine) for conversation flow
- Middleware for auth, logging, rate limiting
- Webhook support for production
- Type-safe with filters (`F.text`, `F.data`)

### 2. python-telegram-bot (PTB) 20.x
```python
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# Command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello!")

# Conversation handler
CHOOSING, CONFIRMING = range(2)

async def swap_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Which token?")
    return CHOOSING

async def token_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['token'] = update.message.text
    keyboard = [[InlineKeyboardButton("Confirm", callback_data="confirm")]]
    await update.message.reply_text(
        f"Swap {context.user_data['token']}?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRMING

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Swapping...")
    return ConversationHandler.END

# Application setup
def main():
    app = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("swap", swap_start)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT, token_chosen)],
            CONFIRMING: [CallbackQueryHandler(confirm, pattern="^confirm$")]
        },
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    app.run_polling()

if __name__ == "__main__":
    main()
```

**PTB Key Features**:
- Mature, stable API
- ConversationHandler for complex flows
- Job queue for scheduled tasks
- Extensive error handling
- Great documentation

---

## 🎯 Architecture Patterns for Trading Bots

### Event-Driven Architecture
```python
# Streaming -> Strategy -> Execution

import asyncio
from solana.rpc.websocket_api import connect
from solders.pubkey import Pubkey

async def monitor_program_accounts(program_id: str, on_update_callback):
    """Subscribe to program account changes"""
    async with connect("wss://your-rpc-ws-endpoint") as websocket:
        await websocket.program_subscribe(
            Pubkey.from_string(program_id),
            commitment="confirmed"
        )
        
        async for msg in websocket:
            account_data = msg.result.value
            await on_update_callback(account_data)

async def trading_strategy(account_data):
    """Analyze and decide"""
    # Parse account data
    # Check profitability
    # Make trade decision
    if should_trade:
        await execute_trade(params)

async def execute_trade(params):
    """Build and send transaction"""
    # Build Jupiter swap
    # Simulate transaction
    # Send with priority fee
    # Monitor confirmation
    pass

# Main loop
async def main():
    await monitor_program_accounts(
        JUPITER_V6_PROGRAM,
        trading_strategy
    )
```

### Webhook Pattern for Telegram
```python
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

bot = Bot(token="TOKEN")
dp = Dispatcher()

async def on_startup(app):
    await bot.set_webhook(
        url=f"https://yourdomain.com/webhook",
        allowed_updates=["message", "callback_query"]
    )

async def on_shutdown(app):
    await bot.delete_webhook()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    
    web.run_app(app, host="0.0.0.0", port=8080)
```

---

## 🚀 Performance Optimization Patterns

### 1. RPC Connection Pooling
```python
from solana.rpc.async_api import AsyncClient
from contextlib import asynccontextmanager

class SolanaRPCPool:
    def __init__(self, rpc_urls: list[str]):
        self.clients = [AsyncClient(url) for url in rpc_urls]
        self.current = 0
    
    @asynccontextmanager
    async def get_client(self):
        client = self.clients[self.current]
        self.current = (self.current + 1) % len(self.clients)
        try:
            yield client
        finally:
            pass

# Usage
pool = SolanaRPCPool([
    "https://rpc1.com",
    "https://rpc2.com",
    "https://rpc3.com"
])

async with pool.get_client() as client:
    balance = await client.get_balance(pubkey)
```

### 2. Transaction Bundle (Jito)
```python
import httpx

async def send_jito_bundle(
    transactions: list[VersionedTransaction],
    tip_lamports: int = 10000
):
    """Send bundle via Jito for MEV protection"""
    
    # Serialize transactions
    serialized_txs = [bytes(tx).hex() for tx in transactions]
    
    # Add tip transaction
    tip_accounts = [
        "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
        "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
        # ... other Jito tip accounts
    ]
    
    bundle = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendBundle",
        "params": [serialized_txs]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://mainnet.block-engine.jito.wtf/api/v1/bundles",
            json=bundle
        )
        return response.json()
```

### 3. Geyser Streaming (Ultra Low Latency)
```python
import grpc
from yellowstone_grpc_proto import geyser_pb2, geyser_pb2_grpc

async def stream_geyser_updates(endpoint: str, token: str, accounts: list[str]):
    """Stream account updates via Yellowstone Geyser"""
    
    credentials = grpc.ssl_channel_credentials()
    channel = grpc.aio.secure_channel(endpoint, credentials)
    stub = geyser_pb2_grpc.GeyserStub(channel)
    
    request = geyser_pb2.SubscribeRequest(
        accounts={
            "client": geyser_pb2.SubscribeRequestFilterAccounts(
                account=[acc for acc in accounts]
            )
        }
    )
    
    metadata = [("x-token", token)]
    stream = stub.Subscribe(request, metadata=metadata)
    
    async for msg in stream:
        if msg.HasField("account"):
            # Process account update
            pubkey = msg.account.account.pubkey
            data = msg.account.account.data
            await process_account_update(pubkey, data)
```

---

## 🔐 Security Best Practices

### Key Management
```python
import os
from solders.keypair import Keypair
from cryptography.fernet import Fernet

# Load from environment
def load_wallet_from_env() -> Keypair:
    secret_key = os.getenv("SOLANA_PRIVATE_KEY")
    if not secret_key:
        raise ValueError("SOLANA_PRIVATE_KEY not set")
    
    # Decrypt if encrypted
    if os.getenv("ENCRYPTION_KEY"):
        fernet = Fernet(os.getenv("ENCRYPTION_KEY").encode())
        secret_key = fernet.decrypt(secret_key.encode()).decode()
    
    return Keypair.from_base58_string(secret_key)

# Never log private keys
def safe_log_wallet(wallet: Keypair):
    print(f"Using wallet: {str(wallet.pubkey())[:8]}...{str(wallet.pubkey())[-8:]}")
```

### Rate Limiting for Telegram
```python
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import TelegramObject
import time

class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: int = 1):
        self.rate_limit = rate_limit
        self.user_last_call: Dict[int, float] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        current_time = time.time()
        
        if user_id in self.user_last_call:
            time_passed = current_time - self.user_last_call[user_id]
            if time_passed < self.rate_limit:
                await event.answer("Too many requests! Wait a moment.")
                return
        
        self.user_last_call[user_id] = current_time
        return await handler(event, data)

# Usage
router.message.middleware(RateLimitMiddleware(rate_limit=2))
```

---

## 📊 Testing Patterns

### Mock Solana RPC for Tests
```python
from unittest.mock import AsyncMock, patch
import pytest

@pytest.fixture
async def mock_solana_client():
    client = AsyncMock()
    client.get_balance.return_value = {"result": {"value": 1000000000}}
    client.send_transaction.return_value = {"result": "signature_here"}
    return client

@pytest.mark.asyncio
async def test_swap_logic(mock_solana_client):
    with patch("your_module.AsyncClient", return_value=mock_solana_client):
        result = await execute_swap(amount=100, token="USDC")
        assert result.success
```

### Test Telegram Handlers
```python
from aiogram.methods import SendMessage
from aiogram.types import User, Chat, Message

@pytest.mark.asyncio
async def test_start_command():
    # Create fake message
    user = User(id=123, is_bot=False, first_name="Test")
    chat = Chat(id=123, type="private")
    message = Message(
        message_id=1,
        date=1234567890,
        chat=chat,
        from_user=user,
        text="/start"
    )
    
    # Test handler
    result = await cmd_start(message)
    assert isinstance(result, SendMessage)
    assert "Welcome" in result.text
```

---

## 🎓 Quick Reference URLs

### Solana
- RPC Docs: https://solana.com/docs/rpc
- WebSocket: https://solana.com/docs/rpc/websocket
- solana-py: https://michaelhly.github.io/solana-py/
- solders: https://kevinheavey.github.io/solders/

### DEX
- Jupiter V6: https://hub.jup.ag/docs/apis/swap-api
- Raydium SDK: https://github.com/raydium-io/raydium-sdk-V2
- Meteora Docs: https://docs.meteora.ag/
- Pyth Feeds: https://docs.pyth.network/price-feeds

### Telegram
- Bot API: https://core.telegram.org/bots/api
- aiogram: https://docs.aiogram.dev/en/latest/
- PTB: https://docs.python-telegram-bot.org/

### BAGS.fm
- API Docs: https://docs.bags.fm/api-reference/introduction
- Program IDs: https://docs.bags.fm/principles/program-ids
- SDK: https://www.npmjs.com/package/@bagsfm/bags-sdk

---

**Last Updated**: 2026-01-25  
**For**: MCP Memory Server + Sequential Thinking  
**Project**: Jarvis Solana Trading Bot
