# The Architect's Guide to Automated On-Chain Intelligence

> Building a Solana-Powered Bot on Telegram
> **Context Document for JARVIS Bot Development**
> Added: 2026-01-12

## Introduction

The Web3 landscape is undergoing a fundamental paradigm shift, moving away from manual, click-driven user interactions toward a new era of automated, event-driven agents. This evolution is powered by the synthesis of high-performance blockchain infrastructure and ubiquitous messaging platforms, which together serve as the ideal foundation for creating sophisticated, low-latency financial tools.

Solana's high-speed architecture, with its sub-second block finality and negligible transaction costs, provides the perfect substrate for systems that must react to market changes in an instant. Simultaneously, Telegram has evolved into a robust application platform, offering programmatic access that allows developers to build rich, interactive experiences.

This guide provides a comprehensive architectural framework for building professional-grade automated systems on this foundation, engineering an autonomous financial reflex that can perceive on-chain events, react intelligently, and communicate its actions through a familiar interface.

---

## 1.0 Foundational Architecture: The Anatomy of a Solana Telegram Bot

Before a single line of code is written, a robust architectural plan is essential for building a scalable and maintainable system. A professional-grade bot is not a monolithic script but a distributed system composed of specialized, interacting components. Engineering a reliable automated agent mandates a precise understanding of the interplay between its four primary subsystems: the user interface, the logic core, the blockchain interface, and the persistence layer.

### 1.1 Deconstructing the System Components

A professional Solana wallet tracking and trading bot is comprised of four primary components, each with a distinct and critical function.

#### The Telegram Interface
This is the user-facing layer of the application, responsible for handling user commands and displaying information via the Telegram Bot API. It acts as the primary user interface, providing an accessible and mobile-friendly way to interact with the system. While users send messages and press buttons here, the actual processing and decision-making occur on the backend.

#### The Backend Service
Functioning as the central nervous system, the backend houses the application's core business logic. It processes user commands received from the Telegram interface, orchestrates interactions with the Solana blockchain, and manages data flow to and from the database. The industry has largely converged on Node.js (with TypeScript) and Rust as the primary development environments for these high-concurrency applications.

#### The Blockchain Connection (RPC & WSS)
This component is the bridge connecting the backend service to the live Solana network. It utilizes two distinct protocols:
- **RPC endpoints**: Used for querying blockchain state, such as fetching transaction details or account balances
- **WSS endpoints**: Provide a real-time, persistent connection that allows the system to subscribe to and receive live on-chain events as they happen, enabling immediate reaction

#### The Persistence Layer (Database)
A database, such as MongoDB or SQLite, is necessary for storing critical information that must persist across sessions. Its primary functions include:
- Managing a historical log of all transactions
- Storing user-specific preferences (like custom slippage or priority fee settings)
- Securely housing encrypted user wallet keys for signing transactions

---

## 2.0 The Core Technology Stack: Assembling the Developer's Toolkit

Selecting the right technical dependencies is a strategic decision that directly impacts an application's performance, reliability, and security. A production-ready bot requires a suite of specialized libraries to efficiently manage blockchain communication, messaging interfaces, data persistence, and cryptographic operations.

### 2.1 Essential Dependencies for a Production-Ready Bot

| Dependency | Domain | Technical Role |
|------------|--------|----------------|
| `@solana/web3.js` | Blockchain | Provides the primary interface for RPC communication, transaction construction, and account management. |
| `Telegraf.js` | Interface | An extensible framework for the Telegram Bot API, facilitating middleware and conversational state. |
| `@jup-ag/api` | Liquidity | The official SDK for interacting with the Jupiter swap aggregator and its intelligent routing engine. |
| `bs58` | Cryptography | Essential for encoding and decoding base58-encoded public and private keys. |
| `dotenv` | Configuration | Manages sensitive environment variables, such as API tokens and RPC endpoints, outside the codebase. |
| `better-sqlite3` | Persistence | A high-performance SQLite driver for local data storage and encrypted key management. |
| `@sentry/node` | Monitoring | Facilitates real-time error tracking and performance monitoring. |

---

## 3.0 Real-Time Perception: Listening to the Solana Blockchain

The effectiveness of any automated agent is defined by its ability to perceive and react to its environment in real time. For a trading bot, this means instantly detecting on-chain events like token swaps, liquidity additions, or balance changes.

### 3.1 Establishing the Connection: RPC Providers

The Solana RPC provider is the bot's gateway to the blockchain. While public endpoints exist, they are heavily rate-limited and fundamentally unsuitable for production applications where reliability and speed are critical. Dedicated providers such as **Helius**, **QuickNode**, or **Ankr** offer low-latency, high-throughput connections necessary for competitive trading.

### 3.2 Subscribing to On-Chain Events: WebSockets vs. Webhooks

There are two primary architectural patterns for receiving real-time on-chain events:

#### Direct WebSocket Subscriptions

**Mechanism**: WebSockets provide a persistent, two-way communication channel between the bot's backend and a Solana node. This allows the node to push raw blockchain events directly to the application the moment they occur.

**SDK Methods**: The `@solana/web3.js` library offers several key subscription methods:
- `onAccountChange` for wallet balance updates
- `onLogs` for new logs emitted by a program
- `onProgramAccountChange` for tracking all accounts owned by a specific program

**Primary Challenge**: This method delivers raw, unprocessed data. The trade-off for this granular control is a significant increase in engineering complexity and operational burden.

**Operational Overhead**: This approach demands robust reconnection logic to handle inevitable network interruptions and server-side error codes, such as `1006` (abnormal closure) or `ECONNRESET`.

#### Managed Webhooks (Helius)

**Mechanism**: Services like Helius offer a higher-level abstraction via webhooks. Instead of maintaining a persistent connection, the bot's backend provides a URL that Helius calls whenever a specific, pre-defined event occurs.

**Offloaded Logic**: This model offloads the complex parsing and interpretation logic to the infrastructure provider. The developer simply subscribes the bot to specific, pre-parsed "Transaction Types" (e.g., `SWAP`, `NFT_SALE`, `TOKEN_TRANSFER`).

**Key Advantage**: The advantage is a dramatic reduction in development velocity, achieved by accepting a dependency on a managed infrastructure provider.

**Ideal Use Case**: This method is ideal for filtering for complex, high-signal events without the overhead of processing every raw transaction involving a monitored address.

> **Architectural Note**: Direct WebSocket subscriptions are the correct choice for bots requiring the lowest possible latency and absolute control over data interpretation, such as high-frequency arbitrage agents. For all other systems, where development velocity and focus on business logic are paramount, the managed webhook model is the superior and more pragmatic engineering decision.

---

## 4.0 The Logic Engine: Transaction Strategy and Execution

After a bot perceives a relevant on-chain event, its core purpose is to construct and execute a transaction in response. To build an effective and reliable trading engine, it is critical to understand Solana's modern transaction lifecycle, navigate the diverse sources of on-chain liquidity, and implement best practices for risk management and fee optimization.

### 4.1 Mastering the Solana Transaction Lifecycle

#### 1. Versioned Transactions

Introduced to overcome the size limitations of legacy transactions, Versioned Transactions (v0) utilize **Address Lookup Tables (ALTs)**. ALTs are on-chain tables that store lists of account addresses. Instead of including a full 32-byte public key for each account in a transaction, a v0 transaction can reference an account by its 1-byte index in an ALT.

This size reduction is not merely an optimization; it is a **strategic imperative** that directly enables more complex atomic arbitrage strategies by fitting more instructions within a single transaction.

#### 2. Atomicity

A core principle of Solana is transaction atomicity. This guarantees that all instructions within a single transaction must succeed for any of the state changes to be committed. If even one instruction fails, the entire transaction is reverted.

This is **strategically valuable for arbitrage bots**, which can bundle a buy instruction on one DEX and a sell instruction on another into a single atomic unit, eliminating the risk of being left with an unwanted position if one leg of the trade fails.

#### 3. Priority Fees and Simulation

To ensure competitive transaction inclusion during periods of high network activity, bots must dynamically calculate priority fees based on recent network conditions rather than using a fixed value.

**Best Practice**: First simulate the transaction using `connection.simulateTransaction()`. This returns the precise number of compute units required, allowing the bot to set an accurate compute budget.

This two-step process—**simulate then execute**—is the cornerstone of reliable execution on Solana.

### 4.2 Navigating Liquidity: Jupiter vs. Raydium

#### Jupiter (Liquidity Aggregator)

Jupiter is an aggregator that intelligently routes trades across multiple DEXs to find the optimal swap route and price. The typical interaction flow:

1. Call the `/quote` API endpoint to get the best available price
2. Once a quote is accepted, call the `/swap` endpoint
3. Receive a fully serialized transaction ready to be signed and sent

#### Raydium (Direct DEX Interaction)

Raydium often serves as the primary liquidity source for newly launched token pairs before they are indexed by aggregators.

**Operational Challenge**: Managing the `mainnet.json` file, which contains metadata for all liquidity pools and can exceed **500 MB**.

**Solution**: Implement a strategy to periodically download this file and "trim" it into a much smaller `trimmed_mainnet.json` containing only the metadata for actively monitored token pairs.

> **Architectural Note**: For bots requiring immediate access to new token pairs, a direct Raydium integration is non-negotiable despite its overhead. For all other use cases, the simplicity and optimal routing of the Jupiter API represent the superior architectural choice.

---

## 5.0 The Voice: Crafting an Interactive Telegram Experience

A bot's advanced technical capabilities are only valuable if they are accessible to the end-user. Telegram provides a rich suite of tools for building sophisticated and interactive user interfaces directly within its messaging app.

### 5.1 Setting Up the Bot

The initial setup process is straightforward and handled via Telegram's official **@BotFather**. By sending a series of simple commands, a developer can:
- Create a new bot profile
- Set its name
- Receive the API access token

### 5.2 Designing the User Interface

| UI Component | Telegram Feature | Technical Application |
|--------------|------------------|----------------------|
| Main Menu | `ReplyKeyboardMarkup` | Display persistent buttons at the bottom of the screen for top-level navigation (e.g., Wallet, Trade, Settings). |
| Action Confirmation | `InlineKeyboardMarkup` | Present dynamic buttons within a message for context-specific actions like confirming a swap or selecting a trade amount. |
| Multi-Step Processes | `WizardScene` (Telegraf.js) | Guide a user through a sequential, state-managed flow for complex tasks like setting a token address and then an amount. |
| Rich Dashboards | Telegram Mini App (TMA) | Embed a full web application (e.g., built with React) for displaying advanced charts and portfolio analytics. |

---

## 6.0 The Guardian: Implementing Robust Security and Key Management

In any system that handles user funds, security is paramount. The single most significant vulnerability in an automated trading bot is the management of private keys.

### 6.1 The Inherent Risk of Server-Side Keys

Storing raw private keys directly within a bot's environment variables or database creates a **single point of catastrophic failure**, rendering all other architectural decisions moot.

Critical vulnerabilities:
- Prime target for attackers seeking to drain user funds
- Susceptible to simple code errors or bugs
- Exposes users to risk of unintended transactions from flawed decision-making loops

### 6.2 The Non-Custodial Paradigm: Scoped Access via TEEs

The modern, secure alternative is to leverage non-custodial infrastructure that utilizes **Trusted Execution Environments (TEEs)**.

Services like **Turnkey** use hardware-isolated environments (such as AWS Nitro Enclaves) to fundamentally change how a bot interacts with a user's wallet:

1. **Isolate Signing**: TEEs create a tamper-proof environment that completely isolates the key generation and transaction signing processes from the bot's main operating system. The raw private key never touches the bot's server.

2. **Define Scoped Policies**: Instead of providing the bot with a raw key, create an "API-only user" for the bot within the TEE service with limited permissions via a fine-grained policy engine.

3. **Example Policy**: Allow the bot to sign transactions that swap one SPL token for another via the Jupiter program, but explicitly forbid any transaction that attempts to transfer native SOL.

> **Architectural Note**: Storing raw private keys on a server is an architectural anti-pattern. The non-custodial model using TEEs is the **required security baseline** for any production application handling user funds.

---

## 7.0 Deployment and Operations: Bringing the Bot to Life

Effective deployment, process management, and operational oversight are crucial for ensuring the system remains reliable, available, and performant.

### 7.1 PM2 vs. Docker: A Comparative Analysis

| Dimension | PM2 (Process Manager) | Docker (Container Platform) |
|-----------|----------------------|----------------------------|
| **Scope** | Manages Node.js processes directly on a host machine. Concerned with keeping the app alive and load balancing across CPU cores. | Packages the application and its entire environment into an isolated container. Concerned with providing a consistent, reproducible environment. |
| **Environment** | Relies on the host system's configuration. Changes to the host can alter the application's behavior. | Ensures the application runs identically on any host that runs Docker, eliminating "it works on my machine" issues. |
| **Isolation** | Provides no inherent resource isolation. Processes share the host's resources and operating system. | Provides strong resource isolation. Each container has its own filesystem, network, and process space. |
| **Scalability** | Offers vertical scalability on a single machine via cluster mode. Horizontal scaling can be complex. | Designed for horizontal scalability. Containers are easily distributed across multiple hosts using orchestrators like Kubernetes. |

> **Architectural Note**: While PM2 offers a low-friction path for single-host deployments, Docker has become the **non-negotiable standard** for professional, scalable systems. The environmental consistency and portability it provides eliminate deployment risks and form the foundation for modern, resilient microservice architectures.

### 7.2 The Hybrid Approach

It is possible to run PM2 inside a Docker container to leverage PM2's cluster mode to fully utilize all available CPU cores within a single container. However, for most modern, multi-node deployments, container orchestration platforms like **Kubernetes** handle this type of resource management and scaling more effectively at the container level.

---

## Conclusion: The Principles of Automated Intelligence

Building a successful automated agent on Solana and Telegram is a multidisciplinary exercise in synthesis. It requires combining:

1. **Real-time data perception** of an event-driven architecture
2. **Robust execution logic** of a well-structured trading engine
3. **User-centric design** of an intuitive interface
4. **Uncompromising standards** of non-custodial security

These systems represent a new frontier in decentralized finance, demonstrating how sophisticated architectural patterns can transform raw, high-velocity on-chain data into autonomous, actionable intelligence.

---

## JARVIS Implementation Status

| Principle | JARVIS Status | Location |
|-----------|---------------|----------|
| Event-driven architecture | ✅ Implemented | `bots/buy_tracker/monitor.py` |
| Jupiter integration | ✅ Implemented | `bots/treasury/jupiter.py` |
| Telegram UI (Inline Keyboards) | ✅ Implemented | `tg_bot/bot.py` |
| WizardScene state machines | ⚠️ Partial | Could improve flows |
| TEE/Non-custodial keys | ❌ Future | Currently encrypted storage |
| Docker deployment | ✅ Available | `Dockerfile` |
| PM2 process management | ⚠️ Optional | Can be added |
| Helius webhooks | ⚠️ Consider | Currently using polling |

---

*Document maintained as part of JARVIS development context*
